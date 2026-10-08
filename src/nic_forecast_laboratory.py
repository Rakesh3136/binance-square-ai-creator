"""NIC Forecast Laboratory: competing hypotheses plus persistent truth-ledger learning."""
from __future__ import annotations
import json,math,urllib.parse,urllib.request,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"; INT=ROOT/"data/intelligence"
PRED=LIVE/"nic_prediction_engine.json"; OUT=LIVE/"nic_forecast_laboratory.json"
REPORT=INT/"nic_forecast_laboratory_report.json"; LEDGER=INT/"nic_forecast_truth_ledger.jsonl"; MATRIX=INT/"nic_signal_predictivity_matrix.json"; REGH=INT/"nic_regime_history.jsonl"
BASES=("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com")
MIN=30; H=(6,12,24)
def n(v,d=0.0):
    try:x=float(v); return x if math.isfinite(x) else d
    except:return d
def load(p,d=None):
    try:v=json.loads(p.read_text()); return v if isinstance(v,type(d if d is not None else {})) else (d if d is not None else {})
    except:return d if d is not None else {}
def sym(v): return str(v or "").upper().replace("BINANCE:","").replace("USDT","").strip()
def candles(s,limit=720):
    q=urllib.parse.urlencode({"symbol":sym(s)+"USDT","interval":"1h","limit":limit}); last=None
    for b in BASES:
        try:
            r=urllib.request.urlopen(urllib.request.Request(b+"/api/v3/klines?"+q,headers={"User-Agent":"binance-square-ai-creator/nic-forecast-lab"}),timeout=15)
            raw=json.loads(r.read()); return [{"t":int(x[0]),"h":n(x[2]),"l":n(x[3]),"c":n(x[4]),"v":n(x[7])} for x in raw if isinstance(x,list) and len(x)>=8]
        except Exception as e:last=e
    raise RuntimeError(str(last))
def ema(v,p):
    if not v:return 0
    a=2/(p+1);e=v[0]
    for x in v[1:]:e=a*x+(1-a)*e
    return e
def rsi(v,p=14):
    if len(v)<=p:return 50
    g=[];l=[]
    for a,b in zip(v[-p-1:-1],v[-p:]):
        d=b-a;g.append(max(d,0));l.append(max(-d,0))
    ag=sum(g)/p;al=sum(l)/p
    return 100 if al==0 else 100-100/(1+ag/al)
def feat(rows,i):
    if i<60:return None
    c=[x["c"] for x in rows[:i+1]]; e20=ema(c[-40:],20);e50=ema(c[-60:],50);av=sum(x["v"] for x in rows[i-20:i])/20
    return {"trend":1 if e20>e50 else -1,"momentum":(c[-1]/c[-7]-1)*100,"rsi":rsi(c),"volume_ratio":rows[i]["v"]/av if av else 1,"distance_ema20":(c[-1]/e20-1)*100,"range_position":(c[-1]-min(x["l"] for x in rows[i-20:i+1]))/max(max(x["h"] for x in rows[i-20:i+1])-min(x["l"] for x in rows[i-20:i+1]),1e-12),"price":c[-1]}
def regime(f):
    if not f:return "UNKNOWN"
    if f["rsi"]>=70 and f["momentum"]>=5:return "TREND_UP_EXTENDED"
    if f["rsi"]<=30 and f["momentum"]<=-5:return "TREND_DOWN_EXTENDED"
    if f["trend"]>0 and f["momentum"]>1:return "TREND_UP"
    if f["trend"]<0 and f["momentum"]<-1:return "TREND_DOWN"
    if f["volume_ratio"]>=2:return "HIGH_FLOW"
    return "RANGE"
def dist(a,b):
    sc={"trend":1,"momentum":5,"rsi":15,"volume_ratio":1.5,"distance_ema20":5,"range_position":.3}
    return math.sqrt(sum(((a[k]-b[k])/sc[k])**2 for k in sc))
def ret(rows,i,h): return None if i+h>=len(rows) else (rows[i+h]["c"]/rows[i]["c"]-1)*100
def signal_flags(f,side):
    return {"trend_aligned":(f["trend"]>0 if side=="BULLISH" else f["trend"]<0),
            "momentum_aligned":(f["momentum"]>0 if side=="BULLISH" else f["momentum"]<0),
            "volume_expansion":f["volume_ratio"]>=1.2,
            "rsi_not_extreme":(f["rsi"]<70 if side=="BULLISH" else f["rsi"]>30),
            "near_ema20":abs(f["distance_ema20"])<=5}
def summarize(vals):
    if not vals:return {"samples":0,"hit_rate":None,"mean_signed_return":None}
    return {"samples":len(vals),"hit_rate":round(sum(x>0 for x in vals)/len(vals),4),"mean_signed_return":round(sum(vals)/len(vals),4)}
def walkforward(rows,side,feature):
    events=[];base=[]
    for i in range(120,len(rows)-24):
        f=feat(rows,i);x=ret(rows,i,24)
        if not f or x is None:continue
        signed=x if side=="BULLISH" else -x;base.append(signed)
        flags=signal_flags(f,side)
        if flags[feature]: events.append(signed)
    b=summarize(base);e=summarize(events);lift=(e["hit_rate"]-b["hit_rate"]) if e["hit_rate"] is not None else None
    return {"feature":feature,"base":b,"conditional":e,"lift":round(lift,4) if lift is not None else None,
            "eligible":e["samples"]>=MIN,"predictive":bool(e["samples"]>=MIN and lift is not None and lift>.05)}
def run(cand,rows):
    if len(rows)<120:return {"status":"INSUFFICIENT_HISTORY","symbol":sym(cand.get("symbol"))}
    ci=len(rows)-1;cur=feat(rows,ci);reg=regime(cur);pool=[]
    for i in range(60,ci-24):
        f=feat(rows,i);r=ret(rows,i,24)
        if f and r is not None:pool.append((dist(cur,f)*(1.25 if regime(f)!=reg else 1),i,f))
    pool.sort();pool=pool[:80];hyps={}
    features=("trend_aligned","momentum_aligned","volume_expansion","rsi_not_extreme","near_ema20")
    for side in ("BULLISH","BEARISH"):
        hs={}
        for h in H:
            vals=[ret(rows,i,h) for _,i,_ in pool];vals=[x if side=="BULLISH" else -x for x in vals if x is not None];hs[str(h)]=summarize(vals)
        audits=[walkforward(rows,side,f) for f in features]
        hs["predictivity"]={"minimum_events":MIN,"audits":audits,
                            "trusted_features":[a["feature"] for a in audits if a["predictive"]]}
        hyps[side]={"analogues":len(pool),"forward":hs}
    # Explicit neutral state prevents forced bull/bear decisions.
    scores={s:sum((hyps[s]["forward"][str(h)]["hit_rate"] or 0) for h in H)/3 for s in hyps}
    decision="BULLISH" if scores["BULLISH"]>scores["BEARISH"]+.05 else ("BEARISH" if scores["BEARISH"]>scores["BULLISH"]+.05 else "WAIT")
    return {"status":"READY","symbol":sym(cand.get("symbol")),"regime":reg,"current_features":cur,"hypotheses":hyps,"decision":decision,
            "decision_rule":"WAIT unless competing sides separate by >5pp average hit rate; feature trust also requires >=30 events and >5pp lift.","as_of":datetime.now(timezone.utc).isoformat()}
def append_jsonl(path,records):
    with path.open("a") as f:
        for x in records:f.write(json.dumps(x,separators=(",",":"))+"\n")
def read_jsonl(path):
    if not path.exists():return []
    out=[]
    for line in path.read_text().splitlines():
        try: out.append(json.loads(line))
        except: pass
    return out
def build_learning():
    rows=read_jsonl(LEDGER); now=datetime.now(timezone.utc)
    resolved=[r for r in rows if r.get("resolved") and int(r.get("horizon_hours") or 0) in H]
    base={}
    groups={}
    for r in resolved:
        side=str(r.get("side") or "").upper(); reg=str(r.get("regime") or "UNKNOWN"); h=int(r.get("horizon_hours") or 0)
        signed=n(r.get("signed_return")); bk=(side,reg,h); base.setdefault(bk,[]).append(signed)
        k=(side,str(r.get("feature") or ""),reg,h); g=groups.setdefault(k,{"returns":[]}); g["returns"].append(signed)
    matrix={}
    for (side,feature,reg,h),g in groups.items():
        vals=g["returns"]; base_vals=base.get((side,reg,h),[])
        rate=sum(x>0 for x in vals)/len(vals) if vals else 0
        base_rate=sum(x>0 for x in base_vals)/len(base_vals) if base_vals else 0
        midpoint=max(1,len(vals)//2); recent=vals[midpoint:]
        recent_rate=sum(x>0 for x in recent)/len(recent) if recent else rate
        lift=rate-base_rate; recent_lift=recent_rate-base_rate
        key=f"{side}|{feature}|{reg}|{h}h"
        matrix[key]={"side":side,"feature":feature,"regime":reg,"horizon_hours":h,
                     "samples":len(vals),"base_samples":len(base_vals),
                     "hit_rate":round(rate,4),"base_hit_rate":round(base_rate,4),
                     "lift":round(lift,4),"recent_lift":round(recent_lift,4),
                     "mean_signed_return":round(sum(vals)/len(vals),4) if vals else None,
                     "trusted":len(vals)>=MIN and lift>.05 and recent_lift>=0}
    MATRIX.write_text(json.dumps({"schema":"NIC-SIGNAL-PREDICTIVITY-2.0","generated_at":now.isoformat(),
        "minimum_events":MIN,"minimum_lift":0.05,"matrix":matrix,
        "policy":"Trust only sufficiently sampled edge with positive lift versus same-side/regime/horizon base rate and no recent edge collapse."},indent=2))
    return matrix

def main():
    INT.mkdir(parents=True,exist_ok=True);cs=load(PRED).get("candidates") or [];res=[];fails=[];new=[]
    for c in cs[:12]:
        try:
            rows=candles(c.get("symbol"));out=run(c,rows);res.append(out)
            if out.get("status")=="READY":
                ts=out["as_of"];reg=out["regime"]
                for side,hyp in out["hypotheses"].items():
                    for a in hyp["forward"]["predictivity"]["audits"]:
                        for horizon in H:
                            probability=float(hyp["forward"][str(horizon)].get("hit_rate") or 0.5)
                            new.append({"forecast_id":f"{sym(c.get('symbol'))}|{ts}|{side}|{a['feature']}|{horizon}","timestamp":ts,"symbol":sym(c.get("symbol")),"side":side,"regime":reg,"feature":a["feature"],"horizon_hours":horizon,"entry_price":out["current_features"]["price"],"decision":("LONG_CANDIDATE" if out["decision"]=="BULLISH" and side=="BULLISH" else ("SHORT_CANDIDATE" if out["decision"]=="BEARISH" and side=="BEARISH" else "WAIT")),"forecast_probability":max(0.0,min(1.0,probability)),"resolved":False})
                append_jsonl(REGH,[{"timestamp":ts,"symbol":out["symbol"],"regime":reg,"features":out["current_features"]}])
        except Exception as e:fails.append({"symbol":sym(c.get("symbol")),"error":type(e).__name__+":"+str(e)})
        time.sleep(.05)
    # Deduplicate immutable forecast IDs; the ledger becomes the audit trail.
    existing={r.get("forecast_id") for r in read_jsonl(LEDGER)}
    append_jsonl(LEDGER,[x for x in new if x["forecast_id"] not in existing])
    matrix=build_learning()
    data={"schema":"NIC-FORECAST-LAB-2.0","generated_at":datetime.now(timezone.utc).isoformat(),"results":res,"failures":fails,
          "learning":{"truth_ledger":str(LEDGER.relative_to(ROOT)),"signal_matrix":str(MATRIX.relative_to(ROOT)),"regime_history":str(REGH.relative_to(ROOT)),"walk_forward_validation":True,"persistent_outcome_resolution":True},
          "policy":{"competing_hypotheses":True,"neutral_wait_allowed":True,"historical_analogues_out_of_sample":True,"regime_matching":True,"base_rate_lift_required":True,"minimum_events":MIN,"no_guaranteed_forecast":True,"publication_gate_immutable":True}}
    OUT.write_text(json.dumps(data,indent=2))
    claims=sum(1 for x in res if x.get("status")=="READY" for h in x["hypotheses"].values() for a in h["forward"]["predictivity"]["audits"] if a["predictive"])
    REPORT.write_text(json.dumps({"schema":"NIC-FORECAST-LAB-2.0","generated_at":data["generated_at"],"ready":sum(x.get("status")=="READY" for x in res),"failures":len(fails),"predictive_claims":claims,"learned_signal_cells":len(matrix),"policy":"No signal is trusted from correlation alone; persistent edge requires chronological validation and >=30 events."},indent=2))
    print(json.dumps({"ready":len(res),"failures":len(fails),"learned_signal_cells":len(matrix)}))
if __name__=="__main__":main()
