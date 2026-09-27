"""Turn thesis history into an auditable, outcome-aware memory layer.

This module does not publish, trade, or rewrite safety gates. It reconciles
existing thesis records with verified prediction/outcome artifacts and emits
ranking telemetry for future research selection.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
LEDGER=INTEL/"thesis_ledger.json"
OUT=LIVE/"thesis_memory.json"; REPORT=INTEL/"thesis_memory_report.json"

def load(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def first(d,*keys):
    for k in keys:
        v=d.get(k)
        if v not in (None,"",[],{}): return v
    return None

def outcome_for(thesis_id, symbol, outcomes):
    records=[]
    raw=first(outcomes,"outcomes","predictions","records",default=[])
    if isinstance(raw,dict): raw=[raw]
    if not isinstance(raw,list): raw=[]
    for item in raw:
        if not isinstance(item,dict): continue
        tid=first(item,"thesis_id","prediction_thesis_id")
        sym=first(item,"symbol","asset","ticker")
        if tid==thesis_id or (symbol and sym==symbol): records.append(item)
    return records[-1] if records else None

def classify(t, outcome):
    if not outcome: return "UNRESOLVED"
    value=first(outcome,"result","outcome","status","prediction_result")
    text=str(value or "").upper()
    if any(x in text for x in ("CONFIRMED","CORRECT","WIN","SUCCESS","HIT")): return "CONFIRMED"
    if any(x in text for x in ("REJECTED","INCORRECT","LOSS","FAILED","FAIL")): return "REJECTED"
    return "RESOLVED"

def main():
    ledger=load(LEDGER); outcomes=load(LIVE/"prediction_outcomes.json")
    raw=ledger.get("theses",[]); raw=raw if isinstance(raw,list) else []
    memory=[]
    for t in raw:
        if not isinstance(t,dict): continue
        tid=first(t,"thesis_id","id") or ""
        symbol=first(t,"symbol","asset","ticker")
        outcome=outcome_for(tid,symbol,outcomes)
        state=classify(t,outcome)
        rec={
            "thesis_id":tid,"symbol":symbol,"thesis":first(t,"thesis","summary","thesis_text"),
            "status":state,"original_status":first(t,"status"),"confidence":first(t,"confidence","confidence_score"),
            "created_at":first(t,"created_at","timestamp"),"evidence_snapshot":first(t,"evidence_snapshot","evidence"),
            "missing_evidence":first(t,"missing_evidence",default=[]),"killer_questions":first(t,"killer_questions",default=[]),
            "outcome":outcome,"last_reconciled_at":datetime.now(timezone.utc).isoformat()
        }
        memory.append(rec)
    counts={k:sum(1 for x in memory if x["status"]==k) for k in ("CONFIRMED","REJECTED","RESOLVED","UNRESOLVED")}
    resolved=[x for x in memory if x["status"] in ("CONFIRMED","REJECTED")]
    confirmation_rate=round(sum(x["status"]=="CONFIRMED" for x in resolved)/len(resolved),4) if resolved else None
    # Research-selection telemetry: resolved theses get precedence over stale unresolved
    # records only as an observable signal; this never bypasses evidence gates.
    candidates=sorted(memory,key=lambda x:(x["status"]=="CONFIRMED", x["status"]=="UNRESOLVED", str(x.get("created_at") or "")),reverse=True)[:20]
    state={
        "schema_version":"NIC-THESIS-MEMORY-2.0","generated_at":datetime.now(timezone.utc).isoformat(),
        "source":"thesis_ledger_plus_verified_prediction_outcomes","memory_policy":"outcomes_update_memory; evidence_gates_remain_authoritative",
        "summary":{"total":len(memory),"counts":counts,"resolved":len(resolved),"confirmation_rate":confirmation_rate},
        "active_memory":memory,
        "research_candidates":candidates,
        "learning_signals":{"confirmed_theses":counts["CONFIRMED"],"rejected_theses":counts["REJECTED"],"unresolved_theses":counts["UNRESOLVED"],"confirmation_rate":confirmation_rate},
        "integrity":{"read_only_to_publication":True,"no_trade_execution":True,"no_gate_bypass":True,"no_private_chain_of_thought":True}
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"THESIS_MEMORY_READY","total":len(memory),"resolved":len(resolved),"confirmation_rate":confirmation_rate},indent=2))

if __name__=="__main__": main()
