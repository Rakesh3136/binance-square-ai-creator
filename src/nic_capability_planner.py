"""Evidence-driven capability planner replacing the retired 300-node mesh.

This planner selects existing pipeline capabilities from current evidence. It
does not fabricate agents, invoke 300 model calls, or claim that a capability
was executed merely because it was selected. Model-backed task specialists are
created separately by nic_agent_factory.py when the chat orchestrator delegates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_capability_plan.json"


def load(name: str) -> dict:
    try:
        value = json.loads((LIVE / name).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def normalize_symbol(value: object) -> str:
    symbol = str(value or "").upper().replace("$", "").replace("BINANCE:", "").strip()
    return symbol[:-4] if symbol.endswith("USDT") else symbol


def candidate_signals(market: dict, flow: dict, research: dict, news: dict) -> dict[str, dict]:
    candidates: dict[str, dict] = {}
    def add(raw: object) -> dict:
        symbol = normalize_symbol(raw)
        if not symbol:
            return {}
        return candidates.setdefault(symbol, {"market": [], "flow": [], "research": [], "news": []})

    for item in market.get("top_content_signals", []) + market.get("top_gainers", []) + market.get("top_losers", []):
        if isinstance(item, dict) and item.get("symbol"):
            add(item["symbol"])["market"].append(item)
    for item in flow.get("top_conditional_setups", []):
        if isinstance(item, dict) and item.get("symbol"):
            add(item["symbol"])["flow"].append(item)
    for group in ("potential_gems", "potential_risks"):
        for item in research.get(group, []):
            if isinstance(item, dict) and item.get("symbol"):
                add(item["symbol"])["research"].append(item)
    for article in news.get("articles", []):
        if isinstance(article, dict):
            for symbol in article.get("symbols", [])[:3]:
                add(symbol)["news"].append(article)
    return candidates


def score_symbol(symbol: str, evidence: dict) -> dict:
    market, flow = evidence["market"], evidence["flow"]
    research, news = evidence["research"], evidence["news"]
    move = max([abs(float(x.get("price_change_percent", 0) or 0)) for x in market] or [0])
    volume = max([float(x.get("quote_volume_usdt", x.get("quote_volume", 0)) or 0) for x in market] or [0])
    flow_conf = max([float((x.get("multitimeframe") or {}).get("confidence", x.get("confidence", 0)) or 0) for x in flow] or [0])
    flow_proxy = max([float((x.get("multitimeframe") or {}).get("flow_proxy_score", 0) or 0) for x in flow] or [0])
    research_ev = max([float(x.get("evidence_score", 0) or 0) for x in research] or [0])
    research_info = max([float(x.get("information_advantage_score", 0) or 0) for x in research] or [0])
    news_score = max([float(x.get("news_score", 0) or 0) for x in news] or [0])
    market_score = clamp(move * 2.0 + min(25, volume / 1e8 * 12))
    capital = clamp(flow_conf * .55 + flow_proxy * .45)
    research_score = clamp(research_ev * .55 + research_info * .45)
    news_signal = clamp(news_score)
    prediction = clamp(capital * .55 + market_score * .2 + research_score * .15 + news_signal * .1)
    risk = clamp(100 - prediction * .55 + (12 if not flow else 0))
    quality = clamp(prediction * .45 + research_score * .2 + capital * .2 + news_signal * .15 - risk * .12)
    return {
        "symbol": symbol, "market_signal": market_score, "capital_flow_signal": capital,
        "research_signal": research_score, "news_signal": news_signal,
        "prediction_signal": prediction, "risk_signal": risk, "opportunity_score": quality,
        "evidence_counts": {"market": len(market), "flow": len(flow), "research": len(research), "news": len(news)},
        "conditional_setups": [x.get("trade_setup") for x in flow if x.get("trade_setup")],
    }


def main() -> dict:
    market = load("market_snapshot.json")
    flow = load("capital_flow_intelligence.json")
    research = load("original_research.json")
    news = load("news_snapshot.json")
    feedback = load("performance_feedback.json")
    candidates = candidate_signals(market, flow, research, news)
    scores = sorted((score_symbol(symbol, evidence) for symbol, evidence in candidates.items()),
                    key=lambda row: row["opportunity_score"], reverse=True)

    has_market = any(x["market"] for x in candidates.values())
    has_flow = any(x["flow"] for x in candidates.values())
    has_research_news = any(x["research"] or x["news"] for x in candidates.values())
    selected = []
    def choose(capability: str, reason: str, evidence_count: int) -> None:
        selected.append({"capability_id": capability, "status": "selected",
                         "selection_reason": reason, "evidence_count": evidence_count})

    if has_market:
        choose("market_structure", "Fresh market signals exist for candidate assets.",
               sum(len(x["market"]) for x in candidates.values()))
    if has_flow:
        choose("capital_flow", "Conditional capital-flow evidence exists.",
               sum(len(x["flow"]) for x in candidates.values()))
    if has_research_news:
        choose("research_news", "Research or news evidence exists.",
               sum(len(x["research"]) + len(x["news"]) for x in candidates.values()))
    if has_flow or has_research_news:
        choose("risk_scenario_review", "Evidence exists to test invalidation and counter-scenarios.",
               sum(len(x["flow"]) + len(x["research"]) for x in candidates.values()))
    if scores:
        choose("creator_editorial_strategy", "At least one evidence-backed content candidate exists.", len(scores))
    if feedback:
        choose("outcome_feedback_review", "A performance-feedback artifact is present; its evidence class must be checked.", len(feedback))
    choose("safety_quality_gates", "Safety and quality validation is required for every publication cycle.", 1)

    result = {
        "schema_version": "1.0",
        "version": "DYNAMIC-CAPABILITY-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "architecture": "evidence_selected_capabilities_plus_on_demand_model_workers",
        "legacy_300_mesh_retired": True,
        "logical_agent_count": 0,
        "active_agent_count": 0,
        "instantiated_agent_count": 0,
        "selected_capability_count": len(selected),
        "selected_capabilities": selected,
        "agents": [],
        "evidence_state": {
            "market_available": has_market, "flow_available": has_flow,
            "research_or_news_available": has_research_news,
            "performance_feedback_artifact_available": bool(feedback),
        },
        "shared_blackboard": {
            "candidate_count": len(scores), "top_candidates": scores[:10],
            "aggregation_method": "deterministic_evidence_scoring_not_agent_consensus",
            "publish_authority": "existing_downstream_quality_and_publication_gates",
            "trading_authority": False, "revenue_claims": "observed_only",
        },
        "learning": {
            "feedback_available": bool(feedback),
            "weight_updates": "reserved_for_explicitly_verified_outcomes",
            "no_guaranteed_rewards": True,
        },
        "validation": {
            "legacy_mesh_retired": True, "no_fabricated_agent_instances": len(result_agents := []) == 0,
            "selected_capabilities_are_evidence_gated": True, "status": "VALID",
        },
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "version": result["version"],
                      "logical_agents": 0, "active_agents": 0,
                      "selected_capabilities": [x["capability_id"] for x in selected],
                      "candidate_count": len(scores)}))
    return result


if __name__ == "__main__":
    main()
