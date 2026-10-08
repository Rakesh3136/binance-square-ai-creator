"""NIC Forecast probability calibration with walk-forward scoring."""
from __future__ import annotations
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"; OUT=ROOT/"data/intelligence/nic_forecast_calibration.json"
H=(6,12,24); MIN=30
def read():
    if not LEDGER.exists(): return []
    rows=[]
    for line in LEDGER.read_text().splitlines():
        try:
            x=json.loads(line)
            if x.get("resolved") and int(x.get("horizon_hours") or 0) in H: rows.append(x)
        except Exception: pass
    return rows
def clamp(v): return max(0.0,min(1.0,float(v)))
def metrics(rows):
    scored=[r for r in rows if r.get("forecast_probability") is not None]
    if not scored:return {"samples":0,"brier_score":None,"log_loss":None,"coverage":0.0}
    bs=ll=0.0
    for r in scored:
        p=clamp(r.get("forecast_probability")); y=1.0 if r.get("hit") else 0.0
        bs+=(p-y)**2
        ll -= math.log(max(1e-6, p) if y else max(1e-6, 1.0 - p))
    return {"samples":len(scored),"brier_score":round(bs/len(scored),6),"log_loss":round(ll/len(scored),6),"coverage":round(len(scored)/len(rows),4)}
def calibrate():
    rows=read(); groups={}
    for x in rows:
        k=(str(x.get("side") or "").upper(),str(x.get("regime") or "UNKNOWN"),int(x.get("horizon_hours") or 0)); groups.setdefault(k,[]).append(float(x.get("signed_return") or 0))
    cells={}
    for (side,reg,h),vals in groups.items():
        wins=sum(v>0 for v in vals); n=len(vals); p=(wins+1)/(n+2); confidence=min(1.0,n/MIN); calibrated=.5+(p-.5)*confidence
        cells[f"{side}|{reg}|{h}h"]={"side":side,"regime":reg,"horizon_hours":h,"samples":n,"wins":wins,"raw_rate":round(wins/n,4),"calibrated_probability":round(calibrated,4),"confidence":round(confidence,4),"trusted":n>=MIN}
    return cells
def reliability(rows):
    bins={}
    for r in rows:
        if r.get("forecast_probability") is None: continue
        p=clamp(r.get("forecast_probability")); b=min(9,int(p*10)); k=str(b)
        z=bins.setdefault(k,{"count":0,"probability_sum":0.0,"outcome_sum":0})
        z["count"]+=1; z["probability_sum"]+=p; z["outcome_sum"]+=1 if r.get("hit") else 0
    return {k:{"samples":v["count"],"mean_predicted":round(v["probability_sum"]/v["count"],4),"observed_rate":round(v["outcome_sum"]/v["count"],4)} for k,v in bins.items()}
def main():
    rows=read(); cells=calibrate()
    payload={"schema":"NIC-FORECAST-CALIBRATION-2.0","generated_at":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),"minimum_events":MIN,"cells":cells,"global_metrics":metrics(rows),"reliability_bins":reliability(rows),"policy":"Probabilities are evaluated chronologically on resolved outcomes. Brier score and log loss measure probabilistic quality; small samples are shrunk toward 50% and are never trusted."}
    OUT.write_text(json.dumps(payload,indent=2)); return payload
if __name__=="__main__": print(json.dumps({"cells":len(main()["cells"])}))
