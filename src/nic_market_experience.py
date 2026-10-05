"""NIC 24.3 — Market Experience Memory.

Turns resolved NIC predictions into bounded, reusable forecasting evidence.
This is not a future oracle: it estimates how similar historical setups behaved
and refuses to create an advantage claim when the sample is too small.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/live/nic_trade_experience_ledger.jsonl"
CAL=ROOT/"data/live/nic_probability_calibration.json"
OUT=ROOT/"data/live/nic_market_experience.json"
TERMINAL={"WIN","TP1","TP2","LOSS","SL","INVALIDATED"}

def read_jsonl(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def f(v, default=None):
    try: return float(v)
    except (TypeError,ValueError): return default

def key(p):
    return (
        str(p.get("setup_type") or "UNKNOWN").upper(),
        str(p.get("side") or "UNKNOWN").upper(),
        str(p.get("timeframe") or "UNKNOWN").upper(),
        str(p.get("market_regime") or "UNKNOWN").upper(),
    )

def build():
    rows=read_jsonl(LEDGER)
    predictions={str(x.get("prediction_id")):x.get("prediction") or {}
                 for x in rows if x.get("record_type")=="PREDICTION_SNAPSHOT"}
    groups=defaultdict(lambda: {"wins":0,"losses":0,"samples":0})
    for x in rows:
        if x.get("record_type")!="OUTCOME_EVENT" or x.get("outcome") not in TERMINAL: continue
        p=predictions.get(str(x.get("prediction_id")))
        if not p: continue
        q=groups[key(p)]
        q["samples"]+=1
        if x.get("outcome") in {"WIN","TP1","TP2"}: q["wins"]+=1
        else: q["losses"]+=1
    profiles=[]
    for k,q in groups.items():
        wr=q["wins"]/q["samples"] if q["samples"] else None
        profiles.append({
            "setup_type":k[0],"side":k[1],"timeframe":k[2],"market_regime":k[3],
            **q,"empirical_win_rate":round(wr,4) if wr is not None else None,
            "status":"ESTABLISHED" if q["samples"]>=25 else "DEVELOPING",
        })
    calibration={}
    try:
        calibration=json.loads(CAL.read_text(encoding="utf-8"))
    except Exception: pass
    adjustment=f(calibration.get("recommended_probability_adjustment"),0.0) or 0.0
    doc={
        "schema":"NIC-MARKET-EXPERIENCE-1.0",
        "version":"24.3-market-experience-memory",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "prediction_snapshots":len(predictions),
        "resolved_outcomes":sum(x.get("record_type")=="OUTCOME_EVENT" and x.get("outcome") in TERMINAL for x in rows),
        "profiles":profiles,
        "probability_calibration":{
            "state":calibration.get("state","UNKNOWN"),
            "recommended_adjustment":round(max(-0.10,min(0.10,adjustment)),4)
        },
        "policy":[
            "Historical experience is descriptive evidence, never a guarantee.",
            "Only terminal resolved outcomes enter profiles.",
            "Profiles with fewer than 25 observations are developing and cannot create a trade.",
            "Probability calibration is bounded to +/-10 percentage points.",
            "Historical records are immutable.",
            "The engine may lower confidence when evidence is weak; it may not manufacture certainty."
        ]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return doc

if __name__=="__main__":
    print(json.dumps(build(),indent=2,ensure_ascii=False))
