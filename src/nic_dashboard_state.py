"""Build NIC Command Center telemetry from the repository's real pipeline artifacts.

This module is read-only with respect to market/publishing decisions. It maps the
cockpit to the actual artifact names emitted by the current creator pipeline so
available specialist results are not incorrectly shown as unavailable.
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
    "adversarial": "adversarial_brain_review.json",
    "counterfactual": "creator_16_0_decision_board.json",
    "research": "creator_17_0_research_state.json",
    "creator_brain": "creator_brain_decision.json",
    "ensemble": "decision_ensemble.json",
    "jev": "jev_decision.json",
    "local_critic": "local_model_critic.json",
    "production": "production_decision.json",
    "publication": "publication_result.json",
    "outcomes": "prediction_outcomes.json",
    "learning": "learning_report.json",
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
    value = first(d, "decision", "action", "status", "state", default="UNAVAILABLE")
    if isinstance(value, bool):
        return "PASS" if value else "BLOCK"
    return str(value).upper()


def production_decision(d: dict) -> str:
    if not d:
        return "UNAVAILABLE"
    if isinstance(d.get("publish"), bool):
        return "PUBLISH_ELIGIBLE" if d["publish"] else "PUBLISH_BLOCKED"
    return decision(d)


def specialist(key: str, d: dict) -> dict:
    if not d:
        return {
            "module": key,
            "available": False,
            "decision": "UNAVAILABLE",
            "confidence": None,
            "reason": "artifact_not_available",
        }
    return {
        "module": key,
        "available": True,
        "decision": decision(d),
        "confidence": first(d, "confidence", "score", "evidence_score", "research_score"),
        "reason": first(d, "reason", "rationale", "summary", "thesis", "recommendation", default="artifact_available"),
    }


def main() -> None:
    docs = {key: load(filename) for key, filename in SOURCES.items()}
    nic = docs["nic_core"]
    mesh = docs["mesh"]

    agents = [specialist(key, docs[key]) for key in (
        "adversarial", "counterfactual", "research", "creator_brain",
        "ensemble", "jev", "local_critic"
    )]

    publication = docs["publication"]
    publication_status = first(
        publication,
        "status", "publication_status", "verification_status",
        default="UNAVAILABLE",
    )
    production = docs["production"]
    production_status = production_decision(production)

    state = {
        "schema_version": "NIC-DASH-1.2",
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
            "production_quality_score": first(production, "quality_score", default=None),
            "publication": publication_status,
            "publication_message": first(publication, "message", "reason", "details", default=""),
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
            key: {"file": filename, "available": bool(docs[key])}
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
        "available_specialists": sum(1 for x in agents if x["available"]),
    }))


if __name__ == "__main__":
    main()
