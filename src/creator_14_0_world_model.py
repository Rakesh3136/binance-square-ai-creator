"""Creator 14.0 — NIC World Model + Regime Memory.

Builds an auditable persistent model of the creator environment and now links
market-regime observations to verified prediction outcomes. The module never
turns missing evidence into confidence and never overrides a frozen prediction
contract.
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
REGIME_MEMORY = ANALYTICS / "nic_regime_memory.json"
REGIME_CONTEXT = LIVE / "nic_regime_context.json"
TRUTH_LEDGER = ANALYTICS / "nic_prediction_truth_ledger.jsonl"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
            except json.JSONDecodeError:
                continue
    except (FileNotFoundError, OSError):
        pass
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rid(value: Any) -> str:
    return "wm14_" + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def regime_bucket(regime: Any) -> str:
    value = str(regime or "UNKNOWN").upper().strip()
    return value if value else "UNKNOWN"


def main() -> int:
    self_state = read_json(ANALYTICS / "creator_13_0_self_state.json", {})
    decision = read_json(LIVE / "creator_13_0_executive_decision.json", {})
    market = read_json(LIVE / "market_snapshot.json", {})
    news = read_json(LIVE / "news_snapshot.json", {})
    brain = read_json(LIVE / "creator_9_0_brain_state.json", {})
    experiment = read_json(LIVE / "creator_12_0_active_experiment.json", {})
    strategy = read_json(ANALYTICS / "strategy_memory.json", {})
    outcomes = read_json(ANALYTICS / "creator_7_2_state.json", {})
    regime = read_json(LIVE / "market_regime_intelligence.json", {})
    truth_rows = read_jsonl(TRUTH_LEDGER)

    sources = {
        "market": {"present": bool(market), "keys": sorted(list(market.keys()))[:30] if isinstance(market, dict) else []},
        "news": {"present": bool(news), "keys": sorted(list(news.keys()))[:30] if isinstance(news, dict) else []},
        "executive": {"present": bool(decision), "action": decision.get("action")},
        "experiment": {"present": bool(experiment), "status": experiment.get("status"), "id": experiment.get("experiment_id")},
        "strategy": {"present": bool(strategy)},
        "outcomes": {"present": bool(outcomes)},
        "regime": {"present": bool(regime), "regime": regime.get("regime"), "confidence": regime.get("confidence")},
        "prediction_truth": {"present": bool(truth_rows), "records": len(truth_rows)},
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
    if not regime:
        gaps.append({"priority": 1, "gap": "market_regime_state", "research": "refresh market-regime evidence"})

    current_regime = regime_bucket(regime.get("regime"))
    terminal = [x for x in truth_rows if x.get("outcome") in {"WIN", "INVALIDATED", "AMBIGUOUS"}]
    regime_stats: dict[str, dict[str, int]] = {}
    for row in terminal:
        bucket = regime_bucket(row.get("regime") or row.get("market_regime"))
        stat = regime_stats.setdefault(bucket, {"terminal": 0, "wins": 0, "invalidated": 0, "ambiguous": 0})
        stat["terminal"] += 1
        outcome = row.get("outcome")
        if outcome == "WIN": stat["wins"] += 1
        elif outcome == "INVALIDATED": stat["invalidated"] += 1
        elif outcome == "AMBIGUOUS": stat["ambiguous"] += 1

    for stat in regime_stats.values():
        stat["win_rate"] = round(stat["wins"] / stat["terminal"], 4) if stat["terminal"] else None

    curiosity = self_state.get("self_model", {}).get("curiosity", 0.5)
    executive_action = str(decision.get("action", "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL"))
    if gaps:
        next_action = "RESEARCH_KNOWLEDGE_GAPS"
    elif executive_action == "RESEARCH_AND_WAIT_FOR_STRONG_SIGNAL":
        next_action = "DEEPEN_HIGHEST_VALUE_UNCERTAINTY"
    else:
        next_action = "MONITOR_AND_UPDATE_WORLD_MODEL"

    world = {
        "schema_version": "14.1",
        "world_model_id": rid({"sources": sources, "next_action": next_action, "regime": current_regime, "terminal": len(terminal)}),
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
            "current_market_regime": current_regime,
            "regime_confidence": regime.get("confidence", "LOW"),
        },
        "regime_memory": {
            "current_regime": current_regime,
            "terminal_truth_records": len(terminal),
            "by_regime": regime_stats,
            "minimum_learning_policy": "do not treat a regime as learned from a tiny sample",
        },
        "next_update_policy": "refresh high-impact or stale evidence before major decisions",
    }
    plan = {
        "schema_version": "14.1",
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
            "no prediction training from pending outcomes",
            "no regime inference from insufficient samples",
        ],
    }

    memory = {
        "schema_version": "1.0-regime-memory",
        "updated_at": now(),
        "current_regime": current_regime,
        "current_regime_confidence": regime.get("confidence", "LOW"),
        "current_regime_evidence": regime.get("evidence", {}),
        "terminal_prediction_records": len(terminal),
        "by_regime": regime_stats,
        "policy": {
            "terminal_outcomes_only": True,
            "ambiguous_never_counts_as_win": True,
            "pending_never_trains": True,
            "insufficient_samples_remain_uncertain": True,
            "regime_context_is_advisory": True,
            "never_overrides_frozen_contract": True,
        },
    }
    context = {
        "schema_version": "1.0",
        "generated_at": now(),
        "regime": current_regime,
        "confidence": regime.get("confidence", "LOW"),
        "evidence": regime.get("evidence", {}),
        "historical_truth": regime_stats.get(current_regime, {"terminal": 0, "wins": 0, "invalidated": 0, "ambiguous": 0, "win_rate": None}),
        "learning_ready": bool(regime_stats.get(current_regime, {}).get("terminal", 0) >= 10),
        "advisory_only": True,
    }

    write_json(WORLD, world)
    write_json(DECISION, plan)
    write_json(REGIME_MEMORY, memory)
    write_json(REGIME_CONTEXT, context)
    write_json(INTEL / "creator_14_0_report.json", {
        "module": "creator_14_0_world_model",
        "generated_at": now(),
        "status": plan["status"],
        "next_action": next_action,
        "knowledge_gap_count": len(gaps),
        "world_model_id": world["world_model_id"],
        "current_regime": current_regime,
        "terminal_prediction_records": len(terminal),
    })

    strategy.setdefault("creator_14_0", {})
    strategy["creator_14_0"] = {
        "world_model_id": world["world_model_id"],
        "status": plan["status"],
        "next_action": next_action,
        "knowledge_gap_count": len(gaps),
        "current_regime": current_regime,
        "regime_memory_records": len(terminal),
    }
    strategy.setdefault("learning_overlay", {})
    strategy["learning_overlay"]["world_model"] = strategy["creator_14_0"]
    write_json(ANALYTICS / "strategy_memory.json", strategy)
    print(json.dumps({"status": plan["status"], "next_action": next_action, "knowledge_gap_count": len(gaps), "current_regime": current_regime, "terminal_prediction_records": len(terminal)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
