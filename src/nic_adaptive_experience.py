"""NIC 23.2 — Adaptive experience derived from the immutable JSONL ledger."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/live/nic_trade_experience_ledger.jsonl"
OUT=ROOT/"data/live/nic_adaptive_experience.json"
MIN_SAMPLES=25
def rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out
def main():
    records=rows()
    predictions={str(x.get("prediction_id")):x.get("prediction",{}) for x in records if x.get("record_type")=="PREDICTION_SNAPSHOT"}
    profiles=defaultdict(lambda:{"wins":0,"losses":0,"samples":0})
    terminal={"WIN","TP1","TP2","LOSS","SL","INVALIDATED"}
    for event in records:
        if event.get("record_type")!="OUTCOME_EVENT" or event.get("outcome") not in terminal: continue
        p=predictions.get(str(event.get("prediction_id")))
        if not p: continue
        key=(str(p.get("setup_type") or "UNKNOWN").upper(),str(p.get("side") or "UNKNOWN").upper(),
             str(p.get("timeframe") or "UNKNOWN").upper(),str(p.get("market_regime") or "UNKNOWN").upper())
        q=profiles[key]; q["samples"]+=1
        q["wins"]+=event["outcome"] in {"WIN","TP1","TP2"}
        q["losses"]+=event["outcome"] in {"LOSS","SL","INVALIDATED"}
    result=[]
    for key,q in profiles.items():
        wr=(q["wins"]/q["samples"]) if q["samples"] else None
        result.append({"setup_type":key[0],"side":key[1],"timeframe":key[2],"market_regime":key[3],
            **q,"empirical_win_rate":round(wr,4) if wr is not None else None,
            "experience_status":"ESTABLISHED" if q["samples"]>=MIN_SAMPLES else "DEVELOPING"})
    doc={"version":"23.2-adaptive-experience","generated_at":datetime.now(timezone.utc).isoformat(),
      "prediction_count":len(predictions),"outcome_count":sum(x.get("record_type")=="OUTCOME_EVENT" for x in records),
      "profiles":result,"policy":["Prediction records are immutable.","Outcomes are separate events.",
      "Only terminal outcomes contribute to experience profiles.","Profiles never modify historical predictions.",
      "Insufficient experience cannot authorize a trade."]}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(doc,indent=2))
if __name__=="__main__": main()
