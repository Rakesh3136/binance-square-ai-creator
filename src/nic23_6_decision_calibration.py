"""NIC 23.6 — shadow decision calibration.

Immutable decision/outcome ledger. This layer observes historical outcomes and
reports calibration; it never changes live trade weights or publication gates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"
DECISION=LIVE/"nic23_5_counterfactual_challenge.json"
LEDGER=LIVE/"nic23_6_decision_ledger.jsonl"
REPORT=LIVE/"nic23_6_calibration_report.json"

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    now=datetime.now(timezone.utc); d=load(DECISION)
    decision_id=str(d.get("decision_id") or "").strip()
    if not decision_id:
        report={"version":"23.6.0","generated_at":now.isoformat(),"status":"NOT_APPLICABLE","decision_records":0,"resolved_records":0,"calibration_buckets":[],"live_weights_changed":False,"publication_gate_changed":False,"reason":"No immutable decision_id was supplied by the current verified decision; no ledger record was created.","policy":["Immutable decision records.","Never invent lifecycle identity for missing decisions.","Only resolved outcomes enter calibration."]}
        REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,indent=2)); return
    outcome=d.get("outcome")
    record={"decision_id":decision_id,"recorded_at":now.isoformat(),"symbol":d.get("symbol"),"decision":d.get("decision"),"direction":d.get("primary_direction"),"confidence":d.get("fusion_score",d.get("confidence")),"regime":d.get("regime"),"outcome":outcome,"source_generated_at":d.get("generated_at"),"source":"nic23_5_counterfactual_challenge.json","immutable":True}
    LIVE.mkdir(parents=True,exist_ok=True)
    existing=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try: existing.append(json.loads(line))
            except Exception: pass
    if not any(x.get("decision_id")==decision_id for x in existing):
        with LEDGER.open("a",encoding="utf-8") as f:f.write(json.dumps(record,separators=(",",":"))+"\n")
        existing.append(record)
    observed=[x for x in existing if isinstance(x.get("outcome"),dict) and x.get("outcome",{}).get("resolved") is True]
    buckets=[]
    for lo,hi in [(0,50),(50,60),(60,70),(70,80),(80,101)]:
        b=[x for x in observed if lo<=float(x.get("confidence") or 0)<hi]
        wins=sum(1 for x in b if bool(x.get("outcome",{}).get("success")))
        buckets.append({"range":f"{lo}-{hi}","samples":len(b),"successes":wins,"observed_success_rate":round(wins/len(b),4) if b else None})
    report={"version":"23.6.0","generated_at":now.isoformat(),"status":"SHADOW","decision_records":len(existing),"resolved_records":len(observed),"calibration_buckets":buckets,"live_weights_changed":False,"publication_gate_changed":False,"policy":["Immutable decision records.","Only resolved outcomes enter calibration.","Calibration is observational until explicitly promoted after sufficient sample size.","Never rewrite historical decisions or outcomes."]}
    REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,indent=2))
if __name__=="__main__":main()
