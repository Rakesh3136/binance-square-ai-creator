"""Build the NIC Command Center telemetry snapshot from committed pipeline truth.

This is deliberately read-only with respect to market/publishing decisions: it
summarizes artifacts produced by the authoritative pipeline and never invents
agent state. A separate workflow refreshes this snapshot after creator commits
so the cockpit reflects the final production/publication state, not an early
mid-cycle snapshot.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_dashboard.json"

SOURCES = {
    "nic_core": "nic_core_state.json",
    "mesh": "agent_mesh_300.json",
    "adversarial": "adversarial_decision.json",
    "counterfactual": "counterfactual_decision.json",
    "research": "research_decision.json",
    "creator_brain": "creator_brain_decision.json",
    "ensemble": "decision_ensemble.json",
    "jev": "jev_decision.json",
    "local_critic": "local_model_critic.json",
    "production": "production_decision.json",
    "publication": "publication_verification.json",
    "publication_result": "publication_result.json",
    "outcomes": "creator_24_1_prediction_outcomes.json",
    "learning": "creator_7_2_learning.json",
    "revenue": "creator_8_4_monetization_feedback.json",
}


def load(name: str) -> dict:
    p = LIVE / name
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def decision(d: dict) -> str:
    value = first(d, "decision", "action", "status", default="UNAVAILABLE")
    if isinstance(value, bool):
        return "PASS" if value else "BLOCK"
    return str(value).upper()


def main() -> None:
    docs = {key: load(filename) for key, filename in SOURCES.items()}
    nic = docs["nic_core"]
    mesh = docs["mesh"]

    agents = []
    for key in ("adversarial", "counterfactual", "research", "creator_brain", "ensemble", "jev", "local_critic"):
        d = docs[key]
        agents.append({
            "module": key,
            "available": bool(d),
            "decision": decision(d) if d else "UNAVAILABLE",
            "confidence": first(d, "confidence", "score", "evidence_score"),
            "reason": first(d, "reason", "rationale", "summary", default="artifact_not_available"),
        })

    publication = docs["publication"] or docs["publication_result"]
    publication_status = first(
        publication,
        "status",
        "verification_status",
        default="UNAVAILABLE",
    )

    production = docs["production"]
    production_status = decision(production) if production else "UNAVAILABLE"

    state = {
        "schema_version": "NIC-DASH-1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "committed_repository_artifacts",
        "refresh_mode": "post_cycle_truth_snapshot",
        "nic": {
            "version": nic.get("nic_version"),
            "symbol": nic.get("symbol"),
            "direction": nic.get("direction"),
            "evidence_score": nic.get("evidence_score"),
            "thesis_id": nic.get("thesis_id"),
            "hook_family": nic.get("hook_family"),
            "thesis": nic.get("editorial_thesis"),
        },
        "mesh": {
            "version": mesh.get("version"),
            "logical_agents": mesh.get("logical_agent_count", 0),
            "active_agents": mesh.get("active_agent_count", 0),
            "validation": mesh.get("validation", {}),
            "evidence_state": mesh.get("evidence_state", {}),
        },
        "agents": agents,
        "pipeline": {
            "ensemble": decision(docs["ensemble"]) if docs["ensemble"] else "UNAVAILABLE",
            "production": production_status,
            "publication": publication_status,
            "publication_message": first(publication, "message", "reason", default=""),
            "publication_proof": first(publication, "publication_proof", "proof", default="none"),
            "post_id": first(publication, "post_id", default=None),
            "jev": {
                "available": bool(docs["jev"]),
                "authoritative": docs["jev"].get("jev_authoritative"),
                "action": docs["jev"].get("action"),
                "error_class": docs["jev"].get("error_class"),
            },
        },
        "learning": {
            "outcomes_available": bool(docs["outcomes"]),
            "learning_available": bool(docs["learning"]),
            "revenue_feedback_available": bool(docs["revenue"]),
            "revenue_policy": "verified_observations_only",
        },
        "artifact_health": {
            key: {
                "file": filename,
                "available": bool(docs[key]),
            }
            for key, filename in SOURCES.items()
        },
        "integrity": {
            "no_simulated_agent_status": True,
            "external_models_required": False,
            "publication_authority": "downstream deterministic gates",
        },
    }

    LIVE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "output": str(OUT),
        "schema_version": state["schema_version"],
        "agents": len(agents),
        "mesh_agents": state["mesh"]["logical_agents"],
        "production": production_status,
        "publication": publication_status,
    }))


if __name__ == "__main__":
    main()
