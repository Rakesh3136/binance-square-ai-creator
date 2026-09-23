"""Build NIC Command Center telemetry from real committed pipeline artifacts.

This module is read-only with respect to market/publishing decisions. It exposes
what the current pipeline actually produced, including decision trace, evidence,
outcome and revenue-learning state. Missing artifacts remain missing; nothing is
simulated as online.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_dashboard.json"

SOURCES = {
    "nic_core": "nic_core_state.json", "mesh": "agent_mesh_300.json",
    "adversarial": "adversarial_brain_review.json", "counterfactual": "creator_16_0_decision_board.json",
    "research": "creator_17_0_research_state.json", "creator_brain": "creator_brain_decision.json",
    "ensemble": "decision_ensemble.json", "jev": "jev_decision.json", "local_critic": "local_model_critic.json",
    "production": "production_decision.json", "publication": "publication_result.json",
    "outcomes": "prediction_outcomes.json", "learning": "learning_report.json",
    "revenue": "creator_8_4_monetization_feedback.json",
}


def load(name: str) -> dict:
    try:
        value = json.loads((LIVE / name).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def decision(d: dict) -> str:
    value = first(d, "decision", "action", "status", "state", default="UNAVAILABLE")
    if isinstance(value, bool): return "PASS" if value else "BLOCK"
    return str(value).upper()


def specialist(key: str, d: dict) -> dict:
    if not d:
        return {"module": key, "available": False, "decision": "UNAVAILABLE", "confidence": None, "reason": "artifact_not_available"}
    return {"module": key, "available": True, "decision": decision(d), "confidence": first(d, "confidence", "score", "evidence_score", "research_score"), "reason": first(d, "reason", "rationale", "summary", "thesis", "recommendation", default="artifact_available")}


def production_status(d: dict) -> str:
    if not d: return "UNAVAILABLE"
    if isinstance(d.get("publish"), bool): return "PUBLISH_ELIGIBLE" if d["publish"] else "PUBLISH_BLOCKED"
    return decision(d)


def artifact_meta(key: str, filename: str, d: dict) -> dict:
    return {"file": filename, "available": bool(d), "generated_at": first(d, "generated_at", "timestamp", "created_at", default=None), "status": decision(d) if d else "UNAVAILABLE"}


def main() -> None:
    docs={k:load(v) for k,v in SOURCES.items()}
    nic=docs["nic_core"]; mesh=docs["mesh"]; prod=docs["production"]; pub=docs["publication"]
    agents=[specialist(k,docs[k]) for k in ("adversarial","counterfactual","research","creator_brain","ensemble","jev","local_critic")]

    pub_status=first(pub,"status","publication_status","verification_status",default="UNAVAILABLE")
    prod_status=production_status(prod)
    jev=docs["jev"]
    outcomes=docs["outcomes"]; learning=docs["learning"]; revenue=docs["revenue"]

    state={
      "schema_version":"NIC-DASH-1.3","generated_at":datetime.now(timezone.utc).isoformat(),
      "source":"committed_repository_artifacts","refresh_mode":"post_cycle_truth_snapshot",
      "nic":{"version":nic.get("nic_version"),"symbol":nic.get("symbol"),"direction":nic.get("direction"),"evidence_score":nic.get("evidence_score"),"thesis_id":nic.get("thesis_id"),"hook_family":nic.get("hook_family"),"thesis":nic.get("editorial_thesis")},
      "mesh":{"version":mesh.get("version"),"logical_agents":mesh.get("logical_agent_count",0),"active_agents":mesh.get("active_agent_count",0),"validation":mesh.get("validation",{}),"evidence_state":mesh.get("evidence_state",{})},
      "agents":agents,
      "decision_trace":[
        {"stage":"signal","status":decision(nic),"evidence":nic.get("evidence_score")},
        {"stage":"adversarial","status":decision(docs["adversarial"]),"reason":first(docs["adversarial"],"reason","summary","recommendation",default=None)},
        {"stage":"counterfactual","status":decision(docs["counterfactual"]),"reason":first(docs["counterfactual"],"reason","summary","recommendation",default=None)},
        {"stage":"research","status":decision(docs["research"]),"reason":first(docs["research"],"reason","summary","recommendation",default=None)},
        {"stage":"ensemble","status":decision(docs["ensemble"]),"reason":first(docs["ensemble"],"reason","summary","recommendation",default=None)},
        {"stage":"jev","status":decision(jev),"authoritative":jev.get("jev_authoritative"),"action":jev.get("action")},
        {"stage":"production","status":prod_status,"quality_score":first(prod,"quality_score",default=None)},
        {"stage":"publication","status":str(pub_status).upper(),"post_id":first(pub,"post_id",default=None)},
      ],
      "pipeline":{"ensemble":decision(docs["ensemble"]) if docs["ensemble"] else "UNAVAILABLE","production":prod_status,"production_quality_score":first(prod,"quality_score",default=None),"publication":pub_status,"publication_message":first(pub,"message","reason","details",default=""),"publication_proof":first(pub,"publication_proof","proof",default="none"),"post_id":first(pub,"post_id",default=None),"jev":{"available":bool(jev),"authoritative":jev.get("jev_authoritative"),"action":jev.get("action"),"error_class":jev.get("error_class")}},
      "learning":{"outcomes_available":bool(outcomes),"learning_available":bool(learning),"revenue_feedback_available":bool(revenue),"outcome_summary":first(outcomes,"summary","status","result",default=None),"learning_summary":first(learning,"summary","status","result",default=None),"revenue_summary":first(revenue,"summary","status","result",default=None),"revenue_policy":"verified_observations_only"},
      "evidence_ledger":{"signal_evidence":nic.get("evidence_score"),"mesh_validation":mesh.get("validation",{}),"specialists_available":sum(1 for a in agents if a["available"]),"specialists_total":len(agents),"publication_proof":first(pub,"publication_proof","proof",default="none")},
      "artifact_health":{k:artifact_meta(k,v,docs[k]) for k,v in SOURCES.items()},
      "integrity":{"no_simulated_agent_status":True,"external_models_required":False,"publication_authority":"downstream deterministic gates","decision_trace_is_observational":True},
    }
    LIVE.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":"OK","output":str(OUT),"schema_version":state["schema_version"],"agents":len(agents),"mesh_agents":state["mesh"]["logical_agents"],"production":prod_status,"publication":pub_status,"available_specialists":sum(1 for a in agents if a["available"]),"learning":state["learning"]},indent=2))

if __name__=="__main__": main()
