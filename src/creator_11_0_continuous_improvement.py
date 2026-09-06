#!/usr/bin/env python3
"""Creator 11.0 — autonomous continuous-improvement decision engine.

Consolidates outcome learning, causal/observational strategy, experiments,
growth portfolio, monetization, autonomous brain decisions, and reliability
signals into a bounded next-improvement plan. It plans improvements; it does
not silently rewrite production code or bypass editorial/publication gates.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "analytics/strategy_memory.json"
FILES = {
    "outcomes": ROOT / "analytics/creator_7_2_state.json",
    "causal": ROOT / "analytics/creator_7_3_strategy.json",
    "experiment": ROOT / "analytics/creator_7_4_experiment_plan.json",
    "portfolio": ROOT / "analytics/creator_7_5_growth_portfolio.json",
    "monetization": ROOT / "analytics/creator_8_0_monetization_engine.json",
    "brain": ROOT / "data/live/creator_9_0_brain_state.json",
    "reliability": ROOT / "analytics/creator_10_0_recovery_state.json",
    "repair": ROOT / "analytics/creator_10_1_repair_state.json",
}
REPORT = ROOT / "data/intelligence/creator_11_0_report.json"
STATE = ROOT / "analytics/creator_11_0_improvement_state.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def main() -> int:
    memory = load(MEMORY, {})
    previous = load(STATE, {"version": "11.0", "history": []})
    sources = {name: load(path, {}) for name, path in FILES.items()}

    reliability_events = sources["reliability"].get("last_events", []) if isinstance(sources["reliability"], dict) else []
    blocked = [e for e in reliability_events if e.get("action") in {"BLOCKED_HUMAN_REVIEW", "ESCALATE_HUMAN_REVIEW"}]
    repair_state = sources["repair"] if isinstance(sources["repair"], dict) else {}
    repair_status = repair_state.get("last_status")

    brain = sources["brain"] if isinstance(sources["brain"], dict) else {}
    brain_action = brain.get("action") or brain.get("decision") or "UNKNOWN"

    monetization = sources["monetization"] if isinstance(sources["monetization"], dict) else {}
    revenue_status = monetization.get("status", "UNKNOWN")

    # Priority order deliberately favors system safety, then reliable learning,
    # then growth/monetization optimization. No revenue is inferred from reach.
    if blocked or repair_status in {"CODE_HEALTH_FAILURE", "REVIEW_REQUIRED"}:
        objective = "RESTORE_RELIABILITY"
        next_action = "DIAGNOSE_BLOCKED_SYSTEM"
        confidence = "HIGH"
    elif brain_action in {"WAIT_FOR_VALID_OPPORTUNITY", "RESEARCH_OR_WAIT"}:
        objective = "IMPROVE_OPPORTUNITY_SELECTION"
        next_action = "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL"
        confidence = "MEDIUM"
    elif revenue_status == "VERIFIED_REVENUE_OBSERVED":
        objective = "OPTIMIZE_VERIFIED_REVENUE_FUNNEL"
        next_action = "RUN_CONTROLLED_REVENUE_REPLICATION"
        confidence = "MEDIUM"
    else:
        objective = "IMPROVE_CONTENT_PERFORMANCE"
        next_action = "RUN_NEXT_ADAPTIVE_EXPERIMENT"
        confidence = "MEDIUM"

    current = {
        "objective": objective,
        "next_action": next_action,
        "confidence": confidence,
        "brain_action": brain_action,
        "revenue_status": revenue_status,
        "blocked_reliability_events": len(blocked),
    }
    plan_id = digest(current)

    improvement = {
        "plan_id": plan_id,
        "generated_at": now(),
        "objective": objective,
        "next_action": next_action,
        "confidence": confidence,
        "priority_order": [
            "SAFETY_AND_RELIABILITY",
            "FACTUAL_AND_EDITORIAL_QUALITY",
            "OPPORTUNITY_SELECTION",
            "CONTROLLED_EXPERIMENTS",
            "GROWTH",
            "VERIFIED_MONETIZATION",
        ],
        "evidence_sources": list(FILES.keys()),
        "constraints": {
            "no_blind_code_rewrites": True,
            "no_quality_gate_bypass": True,
            "no_guaranteed_returns": True,
            "no_fake_engagement": True,
            "no_inferred_revenue": True,
            "one_primary_experiment_variable": True,
        },
    }

    history = previous.get("history", [])
    history.append(improvement)
    previous["history"] = history[-50:]
    previous["last_plan"] = improvement
    previous["version"] = "11.0"
    save(STATE, previous)

    if isinstance(memory, dict):
        memory["creator_11_0"] = improvement
        overlay = memory.setdefault("learning_overlay", {})
        overlay["continuous_improvement"] = improvement
        save(MEMORY, memory)

    report = {
        "version": "11.0",
        "generated_at": now(),
        "status": "IMPROVEMENT_PLAN_READY",
        "improvement": improvement,
        "reliability_blockers": blocked,
        "source_health": {k: bool(v) for k, v in sources.items()},
    }
    save(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
