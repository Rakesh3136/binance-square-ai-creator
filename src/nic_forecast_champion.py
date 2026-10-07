"""NIC Forecast Champion/Challenger: walk-forward selection of probability configurations."""
from __future__ import annotations
import json, math
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
OUT=ROOT/"data/intelligence/nic_forecast_champion.json"
MIN_SAMPLES=30
MIN_BRIER_IMPROVEMENT=0.005
MIN_LOGLOSS_IMPROVEMENT=0.01
RECENT_WINDOW=30

def num(v, d=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else d
    except Exception:
        return d

def load_rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text().splitlines():
        try:
            r=json.loads(line)
            if isinstance(r,dict) and r.get("resolved") and r.get("hit") is not None and r.get("forecast_probability") is not None:
                out.append(r)
        except Exception:
            continue
    return sorted(out, key=lambda r:str(r.get("timestamp") or ""))

def clamp(p):
    return min(.999999,max(.000001,num(p,.5)))

def configs():
    return {
        "BASELINE_RAW": lambda p: clamp(p),
        "CONSERVATIVE": lambda p: clamp(.5 + .75*(p-.5)),
        "CALIBRATED_SHRINK": lambda p: clamp(.5 + .60*(p-.5)),
        "CONFIDENT": lambda p: clamp(.5 + 1.15*(p-.5)),
    }

def metrics(rows, transform):
    if not rows: return {"samples":0,"brier":None,"log_loss":None,"coverage":0.0}
    b=ll=0.0
    for r in rows:
        p=transform(num(r.get("forecast_probability"),.5)); y=1 if r.get("hit") else 0
        b+=(p-y)**2
        ll-=y*math.log(p)+(1-y)*math.log(1-p)
    n=len(rows)
    return {"samples":n,"brier":round(b/n,6),"log_loss":round(ll/n,6),"coverage":1.0}

def evaluate(rows):
    cs=configs()
    overall={k:metrics(rows,v) for k,v in cs.items()}
    recent=rows[-RECENT_WINDOW:] if len(rows)>=RECENT_WINDOW else rows
    recent_metrics={k:metrics(recent,v) for k,v in cs.items()}
    eligible={k:v for k,v in overall.items() if v["samples"]>=MIN_SAMPLES}
    if not eligible:
        return {"state":"NO_CHAMPION","champion":None,"overall":overall,"recent":recent_metrics}
    ranked=sorted(eligible, key=lambda kv:(kv[1]["brier"],kv[1]["log_loss"]))
    best_name,best=ranked[0]
    baseline=overall["BASELINE_RAW"]
    improvement_b=(baseline["brier"]-best["brier"]) if baseline["brier"] is not None else 0
    improvement_l=(baseline["log_loss"]-best["log_loss"]) if baseline["log_loss"] is not None else 0
    recent_best=recent_metrics[best_name]
    recent_base=recent_metrics["BASELINE_RAW"]
    recent_b=(recent_base["brier"]-recent_best["brier"]) if recent_best["brier"] is not None else 0
    recent_l=(recent_base["log_loss"]-recent_best["log_loss"]) if recent_best["log_loss"] is not None else 0
    baseline_name="BASELINE_RAW"
    if best_name!=baseline_name and not (improvement_b>=MIN_BRIER_IMPROVEMENT and improvement_l>=MIN_LOGLOSS_IMPROVEMENT and recent_b>=0 and recent_l>=0):
        best_name=baseline_name
    champion_state="CHAMPION" if best_name else "NO_CHAMPION"
    challengers=[]
    for name,m in overall.items():
        challengers.append({"name":name,"brier":m["brier"],"log_loss":m["log_loss"],"samples":m["samples"],"recent_brier":recent_metrics[name]["brier"],"recent_log_loss":recent_metrics[name]["log_loss"],"state":"CHAMPION" if name==best_name else "CHALLENGER"})
    return {
        "state":champion_state,"champion":best_name,"minimum_samples":MIN_SAMPLES,
        "promotion_rule":{"min_brier_improvement":MIN_BRIER_IMPROVEMENT,"min_log_loss_improvement":MIN_LOGLOSS_IMPROVEMENT,"recent_non_regression":True},
        "overall":overall,"recent":recent_metrics,"challengers":challengers
    }

def main():
    rows=load_rows()
    result=evaluate(rows)
    payload={"schema":"NIC-FORECAST-CHAMPION-1.0","generated_at":datetime.now(timezone.utc).isoformat(),
             "resolved_samples":len(rows),"selection":result,
             "policy":"Champion promotion is walk-forward and out-of-sample only. A challenger must materially improve Brier and log-loss versus the raw baseline and show no recent regression. This artifact is advisory and cannot bypass timing, diversity, cooldown, risk, visual truth, or publication gates."}
    OUT.write_text(json.dumps(payload,indent=2))
    print(json.dumps({"samples":len(rows),"state":result["state"],"champion":result["champion"]}))

if __name__=="__main__": main()
