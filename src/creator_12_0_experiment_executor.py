"""Creator 12.0 — bounded autonomous experiment execution.

Turns the 11.0 improvement decision into an executable experiment contract.
This module prepares the experiment for the existing publisher; it does not
publish, bypass gates, invent data, or modify production code.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def experiment_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "exp12_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def main() -> int:
    improvement = read_json(ANALYTICS / "creator_11_0_improvement_state.json", {})
    plan = read_json(ANALYTICS / "creator_7_4_experiment_plan.json", {})
    strategy = read_json(ANALYTICS / "strategy_memory.json", {})
    brain = read_json(LIVE / "creator_9_0_brain_state.json", {})
    reliability = read_json(ANALYTICS / "creator_10_0_recovery_state.json", {})
    repair = read_json(ANALYTICS / "creator_10_1_repair_state.json", {})
    existing = read_json(LIVE / "creator_12_0_active_experiment.json", {})

    blockers = []
    if str(reliability.get("status", "")).upper() in {"BLOCKED", "CRITICAL", "FAILED"}:
        blockers.append("reliability_blocker")
    if str(repair.get("status", "")).upper() in {"REVIEW_REQUIRED", "BLOCKED"}:
        blockers.append("repair_review_or_block")

    existing_status = str(existing.get("status", "")).upper()
    if existing_status in {"ACTIVE", "RUNNING"}:
        result = {**existing, "checked_at": now(), "status": "ACTIVE"}
        result["execution"] = "CONTINUE_EXISTING_EXPERIMENT"
    elif blockers:
        result = {
            "schema_version": "12.0",
            "status": "BLOCKED",
            "execution": "DO_NOT_EXECUTE",
            "blockers": blockers,
            "reason": "Reliability/review safeguards prevent autonomous experiment execution.",
            "created_at": now(),
        }
    else:
        action = str(improvement.get("next_action", "RUN_NEXT_ADAPTIVE_EXPERIMENT"))
        brain_action = str(brain.get("action", ""))
        if "WAIT" in action.upper() or "RESEARCH" in action.upper() or brain_action in {"RESEARCH_OR_WAIT", "WAIT_FOR_VALID_OPPORTUNITY"}:
            result = {
                "schema_version": "12.0",
                "status": "WAITING",
                "execution": "WAIT_FOR_VALID_OPPORTUNITY",
                "reason": "The autonomous brain does not currently authorize a strong opportunity.",
                "created_at": now(),
            }
        else:
            chosen = plan.get("next_experiment") or plan.get("active_experiment") or {}
            variable = chosen.get("primary_variable") or chosen.get("dimension") or "hook_type"
            treatment = chosen.get("treatment") or chosen.get("treatment_value")
            control = chosen.get("control") or chosen.get("control_value")
            if treatment is None or control is None:
                overlay = strategy.get("learning_overlay", {})
                adaptive = overlay.get("adaptive_experiment", {}) if isinstance(overlay, dict) else {}
                variable = adaptive.get("primary_variable", variable)
                treatment = adaptive.get("treatment", treatment)
                control = adaptive.get("control", control)
            if treatment is None or control is None:
                result = {
                    "schema_version": "12.0",
                    "status": "WAITING",
                    "execution": "WAIT_FOR_EXPERIMENT_DEFINITION",
                    "reason": "No complete treatment/control pair is available; no experiment invented.",
                    "created_at": now(),
                }
            else:
                seed = {
                    "primary_variable": variable,
                    "treatment": treatment,
                    "control": control,
                    "sample_target": int(chosen.get("sample_target", 10)),
                    "objective": chosen.get("objective", "outcome_score"),
                }
                result = {
                    "schema_version": "12.0",
                    "status": "ACTIVE",
                    "execution": "AUTHORIZE_NEXT_CONTROLLED_EXPERIMENT",
                    "experiment_id": experiment_id(seed),
                    "primary_variable": variable,
                    "treatment": treatment,
                    "control": control,
                    "sample_target": seed["sample_target"],
                    "objective": seed["objective"],
                    "started_at": now(),
                    "source": "creator_11_0_continuous_improvement + creator_7_4_adaptive_experiment",
                    "publisher_instruction": "Apply exactly one primary variable; preserve all existing editorial, factual, visual, publication, and safety gates.",
                    "hard_constraints": [
                        "no_fake_engagement",
                        "no_guaranteed_returns",
                        "no_inferred_revenue",
                        "no_quality_gate_bypass",
                        "no_blind_code_changes",
                        "one_primary_experiment_variable",
                    ],
                }

    write_json(LIVE / "creator_12_0_active_experiment.json", result)
    report = {
        "module": "creator_12_0_experiment_executor",
        "generated_at": now(),
        "status": result.get("status"),
        "execution": result.get("execution"),
        "experiment_id": result.get("experiment_id"),
        "primary_variable": result.get("primary_variable"),
        "sample_target": result.get("sample_target"),
        "safety": result.get("hard_constraints", []),
    }
    write_json(INTEL / "creator_12_0_report.json", report)

    strategy.setdefault("creator_12_0", {})
    strategy["creator_12_0"] = result
    strategy.setdefault("learning_overlay", {})
    strategy["learning_overlay"]["autonomous_experiment_execution"] = {
        "status": result.get("status"),
        "experiment_id": result.get("experiment_id"),
        "primary_variable": result.get("primary_variable"),
        "execution": result.get("execution"),
    }
    write_json(ANALYTICS / "strategy_memory.json", strategy)
    print(json.dumps({"status": result.get("status"), "execution": result.get("execution"), "experiment_id": result.get("experiment_id")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
