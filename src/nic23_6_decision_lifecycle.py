"""NIC 23.6 — immutable decision lifecycle + shadow calibration ledger.

Verification/shadow only. Never changes live trade weights or publication gates.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"
DECISION=LIVE/"nic23_4_decision_fusion.json"; ROUTE=LIVE/"signal_first_routing.json"
LEDGER=LIVE/"nic23_6_decision_ledger.jsonl"; OUT=LIVE/"nic23_6_calibration.json"
MAX_AGE=45*60

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception:return {}
def now(): return datetime.now(timezone.utc)
def stamp(d):
    try:return datetime.fromisoformat(str(d.get("generated_at")).replace("Z","+00:00"))
    except Exception:return None
def fresh(d,t):
    s=stamp(d); return s is not None and 0 <= (t-s).total_seconds() <= MAX_AGE

def main():
    t=now(); d=load(DECISION); r=load(ROUTE)
    if not d and not r: status="NOT_APPLICABLE"
    else: status="VERIFIED" if fresh(d,t) or fresh(r,t) else "NOT_APPLICABLE"
    source=d if fresh(d,t) else r if fresh(r,t) else {}
    symbol=str(source.get("symbol") or ((source.get("selected") or {}).get("symbol")) or "").upper()
    decision=str(source.get("decision") or source.get("status") or "UNKNOWN").upper()
    confidence=float(source.get("confidence",source.get("fusion_score",0)) or 0)
    regime=str(source.get("regime") or "UNKNOWN").upper()
    payload={"symbol":symbol,"decision":decision,"confidence":confidence,"regime":regime,"evidence_generated_at":source.get("generated_at"),"observed_at":t.isoformat()}
    decision_id=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:20]
    record={"schema":"NIC23.6","decision_id":decision_id,"created_at":t.isoformat(),"status":status,"immutable":True,**payload}
    if status=="VERIFIED":
        LIVE.mkdir(parents=True,exist_ok=True)
        with LEDGER.open("a",encoding="utf-8") as f:f.write(json.dumps(record,separators=(",",":"))+"\n")
    calibration={"version":"23.6.0","generated_at":t.isoformat(),"status":status,"decision_id":decision_id if status=="VERIFIED" else None,"shadow_only":True,"live_weights_changed":False,"outcome_count":0,"calibration":"INSUFFICIENT_DATA","policy":["Immutable decision snapshot.","No outcome is inferred from an unverified publication.","No live confidence weighting changes until sufficient observed outcomes exist.","Never rewrite historical decisions."]}
    OUT.write_text(json.dumps(calibration,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(calibration,indent=2))
if __name__=="__main__":main()
