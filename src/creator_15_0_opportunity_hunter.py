"""Creator 15.0 — Opportunity Hunter.

Turns the accumulated world model, market/news evidence, experiments, growth,
revenue and executive state into a ranked opportunity board. This is a
selection layer: it never publishes, fabricates evidence, infers revenue, or
bypasses editorial/security gates.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"


def load(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def num(obj: Any, *keys: str) -> float:
    if not isinstance(obj, dict):
        return 0.0
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return 0.0


def text(obj: Any, *keys: str) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def evidence_strength(*objects: Any) -> float:
    score = 0.0
    for obj in objects:
        if isinstance(obj, dict):
            score += min(1.0, len(obj) / 25.0)
        elif isinstance(obj, list):
            score += min(1.0, len(obj) / 10.0)
    return min(1.0, score / max(1, len(objects)))


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    world = load(ANALYTICS / "creator_14_0_world_model.json", {})
    knowledge = load(LIVE / "creator_14_0_knowledge_plan.json", {})
    executive = load(LIVE / "creator_13_0_executive_decision.json", {})
    brain = load(LIVE / "creator_9_0_brain_state.json", {})
    market = load(LIVE / "market_snapshot.json", {})
    flow = load(LIVE / "capital_flow_intelligence.json", {})
    news = load(LIVE / "news_snapshot.json", {})
    growth = load(ANALYTICS / "creator_7_5_growth_portfolio.json", {})
    experiment = load(LIVE / "creator_12_0_active_experiment.json", {})
    revenue = load(ANALYTICS / "creator_8_0_monetization_engine.json", {})
    strategy = load(ANALYTICS / "strategy_memory.json", {})
    memory_path = ANALYTICS / "creator_15_0_opportunity_memory.json"
    memory = load(memory_path, {"seen": [], "decisions": [], "updated_at": now})

    market_top = market.get("top_signal", {}) if isinstance(market, dict) else {}
    flow_top = flow.get("highest_conviction", {}) if isinstance(flow, dict) else {}
    news_items = news.get("items", []) if isinstance(news, dict) else []
    if not isinstance(news_items, list):
        news_items = []

    symbol = text(market_top, "symbol")
    flow_symbol = text(flow_top, "symbol")
    change = abs(num(market_top, "price_change_percent", "change_percent"))
    volume = num(market_top, "quote_volume_usdt", "volume_usdt")
    signal = num(market_top, "content_signal_score", "signal_score")
    flow_score = num(flow_top, "flow_score")
    verified_revenue = num(revenue, "verified_revenue", "revenue_verified", "verified_earnings", "earnings_verified")
    urgent = text(executive, "action", "decision") or text(brain, "action", "decision")

    candidates: list[dict[str, Any]] = []

    def add(kind: str, title: str, why: str, base: float, evidence: float, risk: float = 0.15, primary_symbol: str | None = None, metadata: dict | None = None) -> None:
        if not title:
            return
        novelty = 0.75 if kind in {"BREAKING_NEWS", "MARKET_ANOMALY", "NARRATIVE_SHIFT", "CAPITAL_FLOW"} else 0.55
        urgency_score = min(1.0, (change / 25.0) + (0.35 if kind == "BREAKING_NEWS" else 0.0) + (0.15 if kind == "CAPITAL_FLOW" else 0.0))
        audience = 0.72
        monetization = 0.55 if verified_revenue > 0 else 0.35
        execution = max(0.2, evidence)
        score = 100 * (0.24 * base + 0.18 * evidence + 0.14 * urgency_score + 0.12 * novelty + 0.12 * audience + 0.10 * monetization + 0.10 * execution - 0.10 * risk)
        row = {
            "opportunity_id": f"15-{kind.lower()}-{primary_symbol or symbol or 'general'}-{len(candidates)+1}",
            "category": kind,
            "title": title,
            "why_now": why,
            "primary_symbol": primary_symbol or symbol or None,
            "score": round(max(0.0, min(100.0, score)), 2),
            "evidence_strength": round(evidence, 3),
            "risk": round(risk, 3),
            "monetization_status": "VERIFIED_REVENUE_OBSERVED" if verified_revenue > 0 else "NO_VERIFIED_REVENUE",
            "publishable": evidence >= 0.45 and risk < 0.65,
            "requires_fact_check": True,
            "generated_at": now,
        }
        if metadata:
            row.update(metadata)
        candidates.append(row)

    ev = evidence_strength(market, world, strategy)
    flow_ev = evidence_strength(flow, market, world)
    if flow_symbol and flow_score != 0:
        flow_state = str(flow.get("rotation_state") or "UNKNOWN")
        flow_change = num(flow_top, "return_6h_pct")
        flow_volume_ratio = num(flow_top, "volume_ratio_6h_vs_prior_12h")
        add("CAPITAL_FLOW", f"Track {flow_symbol} capital-flow rotation", f"Relative-strength evidence shows {flow_change:.2f}% 6H movement, {flow_volume_ratio:.2f}x recent-vs-prior volume and flow score {flow_score:.2f}; rotation state: {flow_state}.", 0.88, max(flow_ev, 0.60), 0.30, flow_symbol, {"flow_score": flow_score, "rotation_state": flow_state, "volume_ratio": flow_volume_ratio, "directional_bias": "LONG_BIAS" if flow_score > 0 else "SHORT_BIAS"})

    if symbol and (change >= 8 or signal >= 60):
        add("MARKET_ANOMALY", f"Investigate {symbol} market anomaly", f"Live signal shows {change:.2f}% absolute price movement with content signal {signal:.1f}.", 0.90, max(ev, 0.65), 0.30)

    if news_items:
        first = news_items[0] if isinstance(news_items[0], dict) else {}
        headline = text(first, "title", "headline", "name")
        if headline:
            add("BREAKING_NEWS", headline, "A current news item is available for evidence-first verification and contextual analysis.", 0.92, evidence_strength(news_items, world), 0.35)

    add("EXPLAINER", "Explain the strongest current market signal", "Convert the best verified market evidence into useful context rather than a generic price recap.", 0.70, max(ev, 0.50), 0.18)
    add("DATA_DEEP_DIVE", "Data deep-dive on the strongest opportunity", "Use market, news and outcome evidence to explain what changed and what remains uncertain.", 0.66, max(ev, 0.48), 0.20)
    if experiment:
        add("EXPERIMENT", "Continue the active controlled content experiment", "An active experiment exists; preserve its single primary variable and measure outcomes.", 0.78, evidence_strength(experiment, strategy), 0.12)
    add("NARRATIVE_SHIFT", "Detect and explain a meaningful narrative shift", "Look for a change in the evidence-backed story, not manufactured hype.", 0.62, max(evidence_strength(news, world, strategy), 0.45), 0.25)

    seen = {str(x) for x in memory.get("seen", []) if isinstance(x, str)}
    for candidate in candidates:
        candidate["novelty_adjusted"] = round(1.0 if candidate["opportunity_id"] not in seen else 0.35, 3)
        candidate["score"] = round(candidate["score"] * (0.8 + 0.2 * candidate["novelty_adjusted"]), 2)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    board = {
        "version": "15.0",
        "generated_at": now,
        "decision_mode": "RANK_AND_WAIT_FOR_EVIDENCE",
        "executive_context": urgent,
        "opportunities": candidates[:10],
        "selected": candidates[0] if candidates else None,
        "selection_rule": "highest evidence-aware score; wait if evidence is insufficient",
        "constraints": [
            "no fabricated facts",
            "no guaranteed returns",
            "no fake engagement",
            "no inferred revenue",
            "no quality-gate bypass",
            "no autonomous credential/security changes",
            "opportunity selection does not itself publish",
        ],
    }
    save(LIVE / "creator_15_0_opportunity_board.json", board)
    save(INTEL / "creator_15_0_report.json", {
        "version": "15.0",
        "generated_at": now,
        "status": "OPPORTUNITY_BOARD_READY" if candidates else "NO_OPPORTUNITY",
        "selected_opportunity_id": candidates[0]["opportunity_id"] if candidates else None,
        "candidate_count": len(candidates),
        "verified_revenue": verified_revenue,
        "capital_flow_candidate": flow_top if flow_top else None,
        "research_priority": knowledge.get("next_action") if isinstance(knowledge, dict) else None,
    })

    memory["seen"] = list(dict.fromkeys([*(memory.get("seen", []) if isinstance(memory.get("seen", []), list) else []), *[c["opportunity_id"] for c in candidates[-5:]]]))[-100:]
    memory["decisions"] = [{"at": now, "selected": candidates[0]["opportunity_id"] if candidates else None, "score": candidates[0]["score"] if candidates else 0.0}, *(memory.get("decisions", []) if isinstance(memory.get("decisions", []), list) else [])][:100]
    memory["updated_at"] = now
    save(memory_path, memory)

    print(json.dumps({"status": "OK", "selected": board["selected"], "candidates": len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
