"""Resolve matured forecasts into a separate append-only outcome-event ledger.

Forecast snapshots are never rewritten by this resolver. Existing legacy resolved
rows are read for backward compatibility, but new outcomes are emitted as events.
"""
from __future__ import annotations
import json,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS=ROOT/"data/intelligence/nic_forecast_outcome_events.jsonl"
MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
BASES=("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com")
def load_rows(path=LEDGER):
    if not path.exists(): return []
    out=[]
    for line in path.read_text().splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out
def candles(symbol,start_ms,end_ms):
    q=urllib.parse.urlencode({"symbol":symbol+"USDT","interval":"1h","startTime":start_ms,"endTime":end_ms,"limit":5})
    for b in BASES:
        try: return json.loads(urllib.request.urlopen(b+"/api/v3/klines?"+q,timeout=15).read())
        except Exception: pass
    return []
def existing_event_ids(events):
    return {str(x.get("forecast_id")) for x in events if x.get("event_type")=="FORECAST_RESOLVED" and x.get("forecast_id")}
def resolve(rows, now=None, candle_fetcher=None, existing_events=None):
    now=now or datetime.now(timezone.utc); fetch=candle_fetcher or candles
    events=list(existing_events or []); seen=existing_event_ids(events); cache={}; added=[]
    for x in rows:
        fid=str(x.get("forecast_id") or "")
        if not fid or fid in seen: continue
        # Backward compatibility: preserve old resolved rows, but do not rewrite them.
        if x.get("resolved"):
            try:
                ev={"event_type":"FORECAST_RESOLVED","event_id":fid+"|resolved","forecast_id":fid,
                    "resolved_at":x.get("resolved_at") or now.isoformat(),"symbol":x.get("symbol"),
                    "side":x.get("side"),"regime":x.get("regime"),"feature":x.get("feature"),
                    "horizon_hours":int(x.get("horizon_hours") or 0),"entry_price":x.get("entry_price"),
                    "outcome_price":x.get("outcome_price"),"raw_return":x.get("raw_return"),
                    "signed_return":float(x.get("signed_return",0)),"hit":bool(x.get("hit"))}
                added.append(ev); seen.add(fid)
            except Exception: pass
            continue
        if not x.get("timestamp") or not x.get("horizon_hours") or not x.get("entry_price"): continue
        try:
            ts=datetime.fromisoformat(str(x["timestamp"]).replace("Z","+00:00"))
            due=ts+timedelta(hours=int(x["horizon_hours"]))
        except Exception: continue
        if now<due: continue
        s=str(x.get("symbol","")).upper().replace("USDT","")
        key=(s,int(ts.timestamp()*1000),int(due.timestamp()*1000))
        if key not in cache: cache[key]=fetch(*key)
        eligible=[k for k in cache[key] if isinstance(k,list) and len(k)>=5 and int(k[0])<=int(due.timestamp()*1000)]
        if not eligible: continue
        target=float(max(eligible,key=lambda k:int(k[0]))[4]); entry=float(x["entry_price"])
        if entry<=0 or target<=0: continue
        raw=(target/entry-1)*100; signed=raw if str(x.get("side","")).upper()=="BULLISH" else -raw
        ev={"event_type":"FORECAST_RESOLVED","event_id":fid+"|resolved","forecast_id":fid,
            "resolved_at":now.isoformat(),"symbol":s,"side":x.get("side"),"regime":x.get("regime"),
            "feature":x.get("feature"),"horizon_hours":int(x["horizon_hours"]),"entry_price":entry,
            "outcome_price":target,"raw_return":round(raw,6),"signed_return":round(signed,6),"hit":signed>0}
        added.append(ev); seen.add(fid)
    return added
def append_new_events(events,new):
    known=existing_event_ids(events); out=list(events)
    for ev in new:
        fid=str(ev.get("forecast_id") or "")
        if fid and fid not in known:
            out.append(ev); known.add(fid)
    return out
def rebuild(snapshots,events):
    by_id={str(x.get("forecast_id")):x for x in events if x.get("event_type")=="FORECAST_RESOLVED" and x.get("forecast_id")}
    joined=[]
    legacy={str(x.get("forecast_id")):x for x in snapshots if x.get("resolved") and x.get("forecast_id")}
    for x in snapshots:
        fid=str(x.get("forecast_id") or ""); outcome=by_id.get(fid) or legacy.get(fid)
        if outcome:
            row=dict(x); row["resolved"]=True; row["signed_return"]=float(outcome.get("signed_return",0)); joined.append(row)
    base={}; groups={}
    for x in joined:
        side=str(x.get("side") or "").upper(); reg=str(x.get("regime") or "UNKNOWN"); h=int(x.get("horizon_hours") or 0)
        signed=float(x.get("signed_return",0)); base.setdefault((side,reg,h),[]).append(signed)
        groups.setdefault((side,str(x.get("feature") or ""),reg,h),[]).append(signed)
    matrix={}
    for (side,feature,reg,h),vals in groups.items():
        b=base.get((side,reg,h),[]); rate=sum(x>0 for x in vals)/len(vals); br=sum(x>0 for x in b)/len(b) if b else 0
        mid=max(1,len(vals)//2); recent=vals[mid:]; rr=sum(x>0 for x in recent)/len(recent) if recent else rate
        lift=rate-br; recent_lift=rr-br
        matrix[f"{side}|{feature}|{reg}|{h}h"]={"side":side,"feature":feature,"regime":reg,"horizon_hours":h,
            "samples":len(vals),"base_samples":len(b),"hit_rate":round(rate,4),"base_hit_rate":round(br,4),
            "lift":round(lift,4),"recent_lift":round(recent_lift,4),
            "mean_signed_return":round(sum(vals)/len(vals),4),
            "trusted":len(vals)>=30 and lift>.05 and recent_lift>=0}
    MATRIX.parent.mkdir(parents=True,exist_ok=True)
    MATRIX.write_text(json.dumps({"schema":"NIC-SIGNAL-PREDICTIVITY-3.0","generated_at":datetime.now(timezone.utc).isoformat(),
        "minimum_events":30,"minimum_lift":.05,"matrix":matrix,"resolved_event_count":len(by_id),
        "policy":"Immutable forecast snapshots joined to unique terminal outcome events; minimum sample and recent-edge tests required."},indent=2))
    return matrix
if __name__=="__main__":
    EVENTS.parent.mkdir(parents=True,exist_ok=True)
    snapshots=load_rows(); old_events=load_rows(EVENTS); new=resolve(snapshots,existing_events=old_events)
    merged=append_new_events(old_events,new)
    EVENTS.write_text("\n".join(json.dumps(x,separators=(",",":")) for x in merged)+("\n" if merged else ""))
    matrix=rebuild(snapshots,merged)
    print(json.dumps({"new_outcome_events":len(new),"total_outcome_events":len(merged),"matrix_cells":len(matrix),
        "forecast_snapshots_immutable":True,"duplicate_outcomes_prevented":True},indent=2))
