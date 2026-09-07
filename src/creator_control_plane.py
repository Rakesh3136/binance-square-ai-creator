"""Unified Creator Control Plane.

Coordinates the existing Creator 7-19 capability layers without duplicating
or bypassing them. It produces one machine-readable control decision for the
production pipeline. It never publishes, trades, changes credentials, or
rewrites source code.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"
OUT = LIVE / "creator_control_plane.json"
REPORT = INTEL / "creator_control_plane_report.json"

CAPABILITIES = {
    "7.0": (LIVE / "creator_7_0_brain_state.json", "production_pipeline"),
    "10.0": (ANALYTICS / "creator_10_0_recovery_state.json", "reliability"),
    "10.1": (ANALYTICS / "creator_10_1_repair_state.json", "root_cause_repair"),
    "11.0": (ANALYTICS / "creator_11_0_improvement_state.json", "continuous_improvement"),
    "12.0": (LIVE / "creator_12_0_active_experiment.json", "experimentation"),
    "13.0": (ANALYTICS / "creator_13_0_self_state.json", "self_model"),
    "14.0": (ANALYTICS / "creator_14_0_world_model.json", "world_model"),
    "15.0": (LIVE / "creator_15_0_opportunity_board.json", "opportunity_hunter"),
    "16.0": (LIVE / "creator_16_0_decision_board.json", "counterfactuals"),
    "17.0": (LIVE / "creator_17_0_research_state.json", "active_research"),
    "18.0": (ANALYTICS / "creator_18_0_value_allocation.json", "value_allocation"),
    "19.0": (LIVE / "creator_19_0_improvement_board.json", "self_improvement"),
}


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def status(value: Any) -> str:
    if not isinstance(value, dict):
        return "MISSING"
    for key in ("status", "action", "execution"):
        if value.get(key) is not None:
            return str(value[key]).upper()
    return "READY"


def main() -> int:
    snapshot = {}
    for version, (path, role) in CAPABILITIES.items():
        data = load(path)
        snapshot[version] = {
            "role": role,
            "artifact": str(path.relative_to(ROOT)),
            "status": status(data),
            "available": bool(data),
        }

    blockers = []
    for version in ("10.0", "10.1"):
        s = snapshot[version]["status"]
        if any(word in s for word in ("BLOCK", "CRITICAL", "FAILURE", "FAILED", "REVIEW_REQUIRED")):
            blockers.append(f"creator_{version}_safety_state")

    decision = "ALLOW_PRODUCTION_BRAIN_TO_EVALUATE"
    reason = "Control plane is coordinating existing capability state; production gates remain authoritative."
    if blockers:
        decision = "HOLD_PRODUCTION_FOR_SAFETY"
        reason = "A reliability/repair state indicates a safety or stability blocker."

    experiment = snapshot["12.0"]["status"]
    learning = snapshot["19.0"]["status"]
    plan = {
        "schema_version": "control-plane-1.0",
        "generated_at": now(),
        "decision": decision,
        "reason": reason,
        "blockers": blockers,
        "execution_order": [
            "research_and_market",
            "opportunity_and_world_model",
            "counterfactual_decision",
            "content_and_existing_quality_gates",
            "production_publication_gate",
            "outcome_measurement",
            "experiment_learning",
            "self_improvement_plan",
        ],
        "experiment_state": experiment,
        "learning_state": learning,
        "capabilities": snapshot,
        "hard_constraints": [
            "production_workflow_remains_authoritative",
            "no_quality_gate_bypass",
            "no_fake_engagement",
            "no_guaranteed_returns",
            "no_inferred_revenue",
            "no_trading_or_withdrawals",
            "no_automatic_source_code_rewrites",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({"module": "creator_control_plane", "generated_at": plan["generated_at"], "decision": decision, "blockers": blockers, "capability_count": len(snapshot)}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "decision": decision, "blockers": blockers, "capabilities": len(snapshot)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
