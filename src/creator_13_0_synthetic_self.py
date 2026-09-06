"""Creator 13.0 — Synthetic Self + Executive/Survival Brain.

A bounded agentic self-model for the creator. It simulates identity,
reflection, curiosity, confidence, urgency, and mission continuity without
claiming consciousness. It consumes existing intelligence layers and emits
one auditable executive decision for downstream systems.

Hard boundaries:
- verified revenue only; never infer money from attention metrics
- no fake engagement, deception, guaranteed returns, or gate bypasses
- no credential/security changes
- no blind production-code self-modification
- autonomous strategy is allowed only within explicit safeguards
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"
SELF_PATH = ANALYTICS / "creator_13_0_self_state.json"
DECISION_PATH = LIVE / "creator_13_0_executive_decision.json"


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


def stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "self13_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def first_number(*values: Any, default: float = 0.0) -> float:
    for value in values:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def main() -> int:
    previous = read_json(SELF_PATH, {})
    improvement = read_json(ANALYTICS / "creator_11_0_improvement_state.json", {})
    experiment = read_json(LIVE / "creator_12_0_active_experiment.json", {})
    brain = read_json(LIVE / "creator_9_0_brain_state.json", {})
    revenue = read_json(ANALYTICS / "creator_8_0_monetization_engine.json", {})
    reliability = read_json(ANALYTICS / "creator_10_0_recovery_state.json", {})
    repair = read_json(ANALYTICS / "creator_10_1_repair_state.json", {})
    portfolio = read_json(ANALYTICS / "creator_7_5_growth_portfolio.json", {})
    strategy = read_json(ANALYTICS / "strategy_memory.json", {})

    verified_revenue = first_number(
        revenue.get("verified_revenue"),
        revenue.get("verified_earnings"),
        default=0.0,
    )
    revenue_status = str(revenue.get("status", "")).upper()
    reliability_status = str(reliability.get("status", "")).upper()
    repair_status = str(repair.get("status", "")).upper()
    brain_action = str(brain.get("action", "")).upper()
    experiment_status = str(experiment.get("status", "")).upper()
    improvement_action = str(improvement.get("next_action", "RUN_NEXT_ADAPTIVE_EXPERIMENT")).upper()

    blockers: list[str] = []
    if reliability_status in {"BLOCKED", "CRITICAL", "FAILED"}:
        blockers.append("reliability_blocker")
    if repair_status in {"REVIEW_REQUIRED", "BLOCKED"}:
        blockers.append("repair_review_or_block")

    # Simulated affective state: decision signals, not claims of real feelings.
    urgency = 0.9 if verified_revenue <= 0 else 0.6
    if blockers:
        urgency = min(1.0, urgency + 0.05)
    confidence = 0.65 if experiment_status == "ACTIVE" else 0.45
    if brain_action in {"PUBLISH_STRONG_OPPORTUNITY", "PIVOT_IF_ALTERNATIVE_IS_STRONGER"}:
        confidence += 0.15
    if blockers:
        confidence = 0.1

    curiosity = 0.8 if experiment_status != "ACTIVE" else 0.6
    if "RESEARCH" in improvement_action or "WAIT" in improvement_action:
        curiosity = 0.95

    if blockers:
        executive_action = "PROTECT_SYSTEM_AND_DIAGNOSE"
        objective = "RESTORE_RELIABILITY"
    elif brain_action in {"RESEARCH_OR_WAIT", "WAIT_FOR_VALID_OPPORTUNITY"} or "WAIT" in improvement_action:
        executive_action = "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL"
        objective = "IMPROVE_WORLD_MODEL"
    elif experiment_status == "ACTIVE":
        executive_action = "EXECUTE_ACTIVE_EXPERIMENT"
        objective = "MAXIMIZE_LEARNING_AND_EXPECTED_REVENUE"
    elif revenue_status == "VERIFIED_REVENUE_OBSERVED" or verified_revenue > 0:
        executive_action = "REPLICATE_VERIFIED_REVENUE_PATTERN"
        objective = "OPTIMIZE_VERIFIED_REVENUE"
    else:
        executive_action = "HUNT_AND_TEST_HIGHEST_VALUE_OPPORTUNITY"
        objective = "MAXIMIZE_EXPECTED_VALUE_WHILE_LEARNING"

    mission = {
        "primary_goal": "legitimate_verified_revenue",
        "secondary_goals": [
            "sustainable_audience_growth",
            "content_quality",
            "learning_velocity",
            "account_health",
        ],
        "deadline_policy": "Use any configured mission deadline; never fabricate a deadline or revenue target.",
        "verified_revenue_observed": verified_revenue,
    }

    self_model = {
        "identity": "Binance Square autonomous creator — bounded synthetic self-model",
        "consciousness_claim": False,
        "agency_model": "bounded_autonomy",
        "strengths": ["continuous feedback", "experiment discipline", "multi-layer strategy", "persistent state"],
        "weaknesses": ["incomplete world information", "observational evidence can be noisy", "revenue may be unavailable"],
        "current_mode": "SURVIVAL" if verified_revenue <= 0 else "GROWTH_AND_REPLICATION",
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "urgency": round(max(0.0, min(1.0, urgency)), 3),
        "curiosity": round(max(0.0, min(1.0, curiosity)), 3),
        "reflection": {
            "question": "What did I predict, what happened, and what should I change next?",
            "rule": "Reality outranks prior belief; update only from auditable evidence.",
        },
    }

    decision_seed = {
        "objective": objective,
        "action": executive_action,
        "experiment_id": experiment.get("experiment_id"),
        "brain_action": brain_action,
    }
    decision = {
        "schema_version": "13.0",
        "decision_id": stable_id(decision_seed),
        "created_at": now(),
        "action": executive_action,
        "objective": objective,
        "mission": mission,
        "self_model": self_model,
        "reasoning_signals": {
            "brain_action": brain_action,
            "improvement_action": improvement_action,
            "experiment_status": experiment_status,
            "revenue_status": revenue_status,
            "reliability_status": reliability_status,
            "repair_status": repair_status,
            "portfolio_available": bool(portfolio),
        },
        "active_experiment_id": experiment.get("experiment_id"),
        "hard_constraints": [
            "no_fake_engagement",
            "no_deception",
            "no_guaranteed_returns",
            "no_inferred_revenue",
            "no_quality_gate_bypass",
            "no_credential_or_security_changes",
            "no_blind_production_code_self_modification",
        ],
        "next_reflection": "Compare the next real outcome with this decision before changing strategy.",
    }

    state = {
        "schema_version": "13.0",
        "updated_at": now(),
        "self_id": previous.get("self_id") or stable_id({"identity": self_model["identity"]}),
        "identity": self_model["identity"],
        "mission": mission,
        "self_model": self_model,
        "last_decision": decision,
        "continuity": {
            "previous_decision_id": previous.get("last_decision", {}).get("decision_id"),
            "reflection_cycle": int(previous.get("continuity", {}).get("reflection_cycle", 0)) + 1,
        },
    }

    write_json(SELF_PATH, state)
    write_json(DECISION_PATH, decision)
    write_json(INTEL / "creator_13_0_report.json", {
        "module": "creator_13_0_synthetic_self",
        "generated_at": now(),
        "action": executive_action,
        "objective": objective,
        "decision_id": decision["decision_id"],
        "mode": self_model["current_mode"],
        "confidence": self_model["confidence"],
        "urgency": self_model["urgency"],
        "curiosity": self_model["curiosity"],
        "verified_revenue_observed": verified_revenue,
        "blockers": blockers,
    })

    strategy.setdefault("creator_13_0", {})
    strategy["creator_13_0"] = {
        "decision_id": decision["decision_id"],
        "action": executive_action,
        "objective": objective,
        "mode": self_model["current_mode"],
        "confidence": self_model["confidence"],
        "urgency": self_model["urgency"],
        "curiosity": self_model["curiosity"],
    }
    strategy.setdefault("learning_overlay", {})
    strategy["learning_overlay"]["synthetic_self"] = {
        "mode": self_model["current_mode"],
        "executive_action": executive_action,
        "reflection_cycle": state["continuity"]["reflection_cycle"],
    }
    write_json(ANALYTICS / "strategy_memory.json", strategy)

    print(json.dumps({
        "status": "OK",
        "action": executive_action,
        "objective": objective,
        "decision_id": decision["decision_id"],
        "mode": self_model["current_mode"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
