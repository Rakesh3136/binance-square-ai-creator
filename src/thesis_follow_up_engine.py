"""Thesis-to-content bridge: turn unresolved thesis memory into bounded follow-up opportunities.

This layer never publishes or upgrades a hypothesis into a fact. It only identifies
theses that may deserve a fresh-evidence follow-up; downstream evidence, novelty,
editorial, and production gates remain authoritative.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MEMORY=ROOT/"data/live/thesis_memory.json"
RESEARCH=ROOT/"data/intelligence/deep_coin_research_report.json"
ATTR=ROOT/"analytics/publication_attribution.jsonl"
OUT=ROOT/"data/live/thesis_follow_up_opportunities.json"
REPORT=ROOT/"data/intelligence/thesis_follow_up_report.json"

def load(path, default):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception:
        return default

def rows_jsonl(path):
    rows=[]
    if not path.exists(): return rows
    for line in path.read_text(encoding="utf-8").splitlines()[-100:]:
        try:
            v=json.loads(line)
            if isinstance(v,dict): rows.append(v)
        except Exception: pass
    return rows

def symbol_of(x):
    return str(x.get("symbol") or x.get("asset") or x.get("ticker") or "").upper().strip()

def main():
    memory=load(MEMORY,{})
    research=load(RESEARCH,{})
    theses=memory.get("active_memory",[])
    if not isinstance(theses,list): theses=[]
    research_generated=research.get("generated_at") or research.get("timestamp")
    publications=rows_jsonl(ATTR)
    recent_symbols={symbol_of(x) for x in publications[-30:] if symbol_of(x)}

    candidates=[]
    for t in theses:
        if not isinstance(t,dict): continue
        status=str(t.get("status") or "").upper()
        symbol=symbol_of(t)
        if not symbol or status not in {"UNRESOLVED","CONFIRMED","REJECTED","RESOLVED"}:
            continue
        # A follow-up is a candidate, not a publication decision. Unresolved
        # theses are the primary research pool; resolved theses can be revisited
        # only when the current research layer provides a new evidence snapshot.
        priority="HIGH" if status=="UNRESOLVED" else "MEDIUM"
        candidates.append({
            "thesis_id":t.get("thesis_id"),
            "symbol":symbol,
            "original_thesis":t.get("thesis"),
            "thesis_status":status,
            "confidence":t.get("confidence"),
            "created_at":t.get("created_at"),
            "missing_evidence":t.get("missing_evidence") or [],
            "killer_questions":t.get("killer_questions") or [],
            "verified_outcome":t.get("outcome"),
            "current_research_timestamp":research_generated,
            "previously_published_symbol":symbol in recent_symbols,
            "priority":priority,
            "eligibility":"REQUIRES_NEW_VERIFIED_EVIDENCE_AND_MATERIALLY_NEW_PAYOFF",
        })
    # Keep deterministic ordering and avoid an oversized artifact.
    candidates.sort(key=lambda x:(x["priority"]!="HIGH", str(x.get("created_at") or ""), str(x.get("thesis_id") or "")))
    state={
        "schema_version":"NIC-THESIS-FOLLOW-UP-1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY",
        "policy":{
            "hypothesis_never_presented_as_fact":True,
            "follow_up_requires_new_verified_evidence":True,
            "follow_up_requires_materially_new_information":True,
            "successful_post_never_repeated_verbatim":True,
            "resolved_thesis_revisit_is_conditional":True,
            "signal_first_and_quality_gates_authoritative":True,
            "no_private_chain_of_thought":True,
        },
        "current_research_timestamp":research_generated,
        "candidate_count":len(candidates),
        "opportunities":candidates[:25],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({
        "schema_version":state["schema_version"],
        "generated_at":state["generated_at"],
        "candidate_count":len(candidates),
        "unresolved_candidates":sum(x["thesis_status"]=="UNRESOLVED" for x in candidates),
        "output":str(OUT.relative_to(ROOT)),
    },indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"THESIS_FOLLOW_UP_READY","candidate_count":len(candidates),"unresolved_candidates":sum(x["thesis_status"]=="UNRESOLVED" for x in candidates)}))

if __name__=="__main__":
    main()
