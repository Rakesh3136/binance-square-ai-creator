"""Creator 14.0 — World Model + Active Knowledge Acquisition.

Builds an auditable, persistent model of the creator's environment from
existing repository snapshots and intelligence artifacts. It identifies
knowledge gaps and creates bounded research priorities for the next cycle.
It does not fabricate facts and does not claim consciousness.
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
WORLD = ANALYTICS / "creator_14_0_world_model.json"
DECISION = LIVE / "creator_14_0_knowledge_plan.json"


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


def rid(value: Any) -> str:
    return "wm14_" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def main() -> int:
    self_state = read_json(ANALYTICS / "creator_13_0_self_state.json", {})
    decision = read_json(LIVE / "creator_13_0_executive_decision.json", {})
    market = read_json(LIVE / "market_snapshot.json", {})
    news = read_json(LIVE / "news_snapshot.json", {})
    brain = read_json(LIVE / "creator_9_0_brain_state.json", {})
    experiment = read_json(LIVE / "creator_12_0_active_experiment.json", {})
    strategy = read_json(ANALYTICS / "strategy_memory.json", {})
    outcomes = read_json(ANALYTICS / "creator_7_2_state.json", {})

    sources = {
        "market": {"present": bool(market), "keys": sorted(list(market.keys()))[:30] if isinstance(market, dict) else []},
        "news": {"present": bool(news), "keys": sorted(list(news.keys()))[:30] if isinstance(news, dict) else []},
        "executive": {"present": bool(decision), "action": decision.get("action")},
        "experiment": {"present": bool(experiment), "status": experiment.get("status"), "id": experiment.get("experiment_id")},
        "strategy": {"present": bool(strategy)},
        "outcomes": {"present": bool(outcomes)},
    }

    gaps = []
    if not market:
        gaps.append({"priority": 1, "gap": "live_market_state", "research": "refresh verified market data"})
    if not news:
        gaps.append({"priority": 1, "gap": "news_state", "research": "refresh authoritative news discovery"})
    if not brain:
        gaps.append({"priority": 2, "gap": "executive_opportunity_context", "research": "refresh opportunity intelligence"})
    if not experiment:
        gaps.append({"priority": 3, "gap": "experiment_context", "research": "obtain the current adaptive experiment decision"})
    if not strategy:
        gaps.append({"priority": 2, "gap": "strategy_memory", "research": "restore strategy memory before acting"})
    if not outcomes:
        gaps.append({"priority": 3, "gap": "outcome_history", "research": "collect verified performance outcomes"})

    curiosity = self_state.get("self_model", {}).get("curiosity", 0.5)
    executive_action = str(decision.get("action", "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL"))
    if gaps:
        next_action = "RESEARCH_KNOWLEDGE_GAPS"
    elif executive_action == "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL":
        next_action = "DEEPEN_HIGHEST_VALUE_UNCERTAINTY"
    else:
        next_action = "MONITOR_AND_UPDATE_WORLD_MODEL"

    world = {
        "schema_version": "14.0",
        "world_model_id": rid({"sources": sources, "next_action": next_action}),
        "updated_at": now(),
        "scope": "Binance Square creator environment",
        "epistemic_policy": "verified evidence outranks assumptions; missing data is represented as uncertainty",
        "sources": sources,
        "knowledge_gaps": gaps,
        "environment_signals": {
            "market_available": bool(market),
            "news_available": bool(news),
            "executive_action": executive_action,
            "active_experiment": experiment.get("experiment_id"),
            "curiosity_signal": curiosity,
        },
        "next_update_policy": "refresh high-impact or stale evidence before major decisions",
    }
    plan = {
        "schema_version": "14.0",
        "created_at": now(),
        "status": "RESEARCH_REQUIRED" if gaps else "MONITORING",
        "next_action": next_action,
        "priority_research": sorted(gaps, key=lambda x: x["priority"])[:5],
        "world_model_id": world["world_model_id"],
        "hard_constraints": [
            "no fabricated facts",
            "no unsupported market claims",
            "no deceptive behavior",
            "no quality_gate_bypass",
            "no inferred revenue",
        ],
    }

    write_json(WORLD, world)
    write_json(DECISION, plan)
    write_json(INTEL / "creator_14_0_report.json", {
        "module": "creator_14_0_world_model",
        "generated_at": now(),
        "status": plan["status"],
        "next_action": next_action,
        "knowledge_gap_count": len(gaps),
        "world_model_id": world["world_model_id"],
    })

    strategy.setdefault("creator_14_0", {})
    strategy["creator_14_0"] = {
        "world_model_id": world["world_model_id"],
        "status": plan["status"],
        "next_action": next_action,
        "knowledge_gap_count": len(gaps),
    }
    strategy.setdefault("learning_overlay", {})
    strategy["learning_overlay"]["world_model"] = strategy["creator_14_0"]
    write_json(ANALYTICS / "strategy_memory.json", strategy)
    print(json.dumps({"status": plan["status"], "next_action": next_action, "knowledge_gap_count": len(gaps)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
