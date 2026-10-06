"""Resolve matured NIC Forecast Laboratory forecasts without look-ahead."""
from __future__ import annotations
import json,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"; MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
BASES=("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com")
def load_rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text().splitlines():
        try: out.append(json.loads(line))
        except: pass
    return out
def candles(symbol,start_ms,end_ms):
    q=urllib.parse.urlencode({"symbol":symbol+"USDT","interval":"1h","startTime":start_ms,"endTime":end_ms,"limit":5})
    for b in BASES:
        try: return json.loads(urllib.request.urlopen(b+"/api/v3/klines?"+q,timeout=15).read())
        except Exception: pass
    return []
def resolve(rows):
    now=datetime.now(timezone.utc); changed=0; cache={}
    for x in rows:
        if x.get("resolved") or not x.get("timestamp") or not x.get("horizon_hours") or not x.get("entry_price"): continue
        try: ts=datetime.fromisoformat(x["timestamp"].replace("Z","+00:00")); due=ts+timedelta(hours=int(x["horizon_hours"]))
        except: continue
        if now<due: continue
        s=str(x.get("symbol","")).upper().replace("USDT",""); key=(s,int(ts.timestamp()*1000),int(due.timestamp()*1000))
        if key not in cache: cache[key]=candles(*key)
        if not cache[key]: continue
        eligible=[k for k in cache[key] if isinstance(k,list) and len(k)>=5 and int(k[0])<=int(due.timestamp()*1000)]
        if not eligible: continue
        target=float(max(eligible,key=lambda k:int(k[0]))[4]); entry=float(x["entry_price"]); raw=(target/entry-1)*100; signed=raw if x.get("side")=="BULLISH" else -raw
        x.update({"resolved":True,"resolved_at":now.isoformat(),"outcome_price":target,"raw_return":round(raw,6),"signed_return":round(signed,6),"hit":signed>0}); changed+=1
    LEDGER.write_text("\n".join(json.dumps(x,separators=(",",":")) for x in rows)+"\n"); return rows,changed
def rebuild(rows):
    groups={}; base={}
    for x in rows:
        if not x.get("resolved"): continue
        side=str(x.get("side") or "").upper(); reg=str(x.get("regime") or "UNKNOWN"); h=int(x.get("horizon_hours") or 0); signed=float(x.get("signed_return",0))
        base.setdefault((side,reg,h),[]).append(signed)
        k=(side,str(x.get("feature") or ""),reg,h); groups.setdefault(k,[]).append(signed)
    matrix={}
    for (side,feature,reg,h),vals in groups.items():
        b=base.get((side,reg,h),[]); rate=sum(x>0 for x in vals)/len(vals); br=sum(x>0 for x in b)/len(b) if b else 0
        mid=max(1,len(vals)//2); recent=vals[mid:]; rr=sum(x>0 for x in recent)/len(recent) if recent else rate
        lift=rate-br; recent_lift=rr-br
        matrix[f"{side}|{feature}|{reg}|{h}h"]={"side":side,"feature":feature,"regime":reg,"horizon_hours":h,
            "samples":len(vals),"base_samples":len(b),"hit_rate":round(rate,4),"base_hit_rate":round(br,4),
            "lift":round(lift,4),"recent_lift":round(recent_lift,4),
            "mean_signed_return":round(sum(vals)/len(vals),4),"trusted":len(vals)>=30 and lift>.05 and recent_lift>=0}
    MATRIX.write_text(json.dumps({"schema":"NIC-SIGNAL-PREDICTIVITY-2.0","generated_at":datetime.now(timezone.utc).isoformat(),
        "minimum_events":30,"minimum_lift":0.05,"matrix":matrix,
        "policy":"Trust persistent edge only after sufficient resolved observations, positive base-rate lift, and no recent edge collapse."},indent=2)); return matrix

if __name__=="__main__":
    rows,changed=resolve(load_rows()); print(json.dumps({"resolved":changed,"matrix_cells":len(rebuild(rows))}))
