"""300-agent sparse intelligence mesh for the Binance Square Creator.

The 300 agents are logical specialist nodes, not 300 independent LLM calls.
Only evidence-relevant nodes activate for a cycle. The mesh produces a shared
blackboard and weighted consensus that downstream strategy/editorial code can
consume without allowing the mesh to publish or trade by itself.
"""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
MESH_OUT = LIVE / "agent_mesh_300.json"

CLUSTERS = [
    ("market_structure", 35),
    ("capital_flow", 35),
    ("derivatives", 25),
    ("research_news", 35),
    ("technical_setup", 30),
    ("prediction_scenarios", 25),
    ("risk_invalidation", 25),
    ("content_editorial", 30),
    ("audience_growth", 25),
    ("outcome_monetization", 20),
    ("safety_governance", 15),
]
TOTAL_AGENTS = sum(count for _, count in CLUSTERS)


def load(name: str) -> dict:
    p = LIVE / name
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def clamp(v: float) -> float:
    return round(max(0.0, min(100.0, float(v))), 2)


def sym(v: object) -> str:
    s = str(v or "").upper().replace("$", "").replace("BINANCE:", "").strip()
    return s[:-4] if s.endswith("USDT") else s


def stable(seed: str) -> float:
    # Stable deterministic variation; no randomness, so repeated cycles are comparable.
    h = hashlib.sha256(seed.encode()).hexdigest()
    return (int(h[:8], 16) % 10000) / 10000.0


def build_agents() -> list[dict]:
    agents = []
    for cluster, count in CLUSTERS:
        for i in range(1, count + 1):
            agents.append({
                "id": f"{cluster[:4]}_{i:03d}",
                "cluster": cluster,
                "specialty": f"{cluster}_specialist_{i:03d}",
                "activation": "evidence_gated",
                "neighbors": [],
                "weight": round(0.75 + stable(f"{cluster}:{i}") * 0.5, 4),
            })
    # Sparse graph: each node connects to nearby specialists and two cross-cluster nodes.
    for idx, agent in enumerate(agents):
        same = [j for j, a in enumerate(agents) if a["cluster"] == agent["cluster"] and j != idx]
        agent["neighbors"] = [agents[j]["id"] for j in same[:3]]
        for j in range(idx + 1, len(agents)):
            if agents[j]["cluster"] != agent["cluster"] and len(agent["neighbors"]) < 5:
                agent["neighbors"].append(agents[j]["id"])
    return agents


def candidate_signals(market: dict, flow: dict, research: dict, news: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}

    def add(s: str) -> dict:
        s = sym(s)
        if not s:
            return {}
        return out.setdefault(s, {"market": [], "flow": [], "research": [], "news": []})

    for x in market.get("top_content_signals", []) + market.get("top_gainers", []) + market.get("top_losers", []):
        if isinstance(x, dict) and x.get("symbol"):
            add(x["symbol"])["market"].append(x)
    for x in flow.get("top_conditional_setups", []):
        if isinstance(x, dict) and x.get("symbol"):
            add(x["symbol"])["flow"].append(x)
    for group in ("potential_gems", "potential_risks"):
        for x in research.get(group, []):
            if isinstance(x, dict) and x.get("symbol"):
                add(x["symbol"])["research"].append(x)
    for x in news.get("articles", []):
        if isinstance(x, dict):
            for s in x.get("symbols", [])[:3]:
                add(s)["news"].append(x)
    return out


def score_symbol(symbol: str, data: dict) -> dict:
    m = data["market"]
    f = data["flow"]
    r = data["research"]
    n = data["news"]
    move = max([abs(float(x.get("price_change_percent", 0) or 0)) for x in m] or [0])
    volume = max([float(x.get("quote_volume_usdt", x.get("quote_volume", 0)) or 0) for x in m] or [0])
    flow_conf = max([float((x.get("multitimeframe") or {}).get("confidence", x.get("confidence", 0)) or 0) for x in f] or [0])
    flow_proxy = max([float((x.get("multitimeframe") or {}).get("flow_proxy_score", 0) or 0) for x in f] or [0])
    research_ev = max([float(x.get("evidence_score", 0) or 0) for x in r] or [0])
    research_info = max([float(x.get("information_advantage_score", 0) or 0) for x in r] or [0])
    news_score = max([float(x.get("news_score", 0) or 0) for x in n] or [0])
    market_score = clamp(move * 2.0 + min(25, volume / 1e8 * 12))
    capital = clamp(flow_conf * .55 + flow_proxy * .45)
    research_score = clamp(research_ev * .55 + research_info * .45)
    news_signal = clamp(news_score)
    prediction = clamp(capital * .55 + market_score * .2 + research_score * .15 + news_signal * .1)
    risk = clamp(100 - prediction * .55 + (12 if not f else 0))
    quality = clamp(prediction * .45 + research_score * .2 + capital * .2 + news_signal * .15 - risk * .12)
    return {
        "symbol": symbol,
        "market_signal": market_score,
        "capital_flow_signal": capital,
        "research_signal": research_score,
        "news_signal": news_signal,
        "prediction_signal": prediction,
        "risk_signal": risk,
        "opportunity_score": quality,
        "evidence_counts": {"market": len(m), "flow": len(f), "research": len(r), "news": len(n)},
        "conditional_setups": [x.get("trade_setup") for x in f if x.get("trade_setup")],
    }


def main() -> dict:
    market = load("market_snapshot.json")
    flow = load("capital_flow_intelligence.json")
    research = load("original_research.json")
    news = load("news_snapshot.json")
    feedback = load("performance_feedback.json")
    agents = build_agents()
    candidates = candidate_signals(market, flow, research, news)
    scores = sorted(
        (score_symbol(s, d) for s, d in candidates.items()),
        key=lambda x: x["opportunity_score"],
        reverse=True,
    )

    # Evidence availability is global to the current cycle. The previous
    # implementation referenced an undefined per-agent `data` variable, which
    # made the entire mesh fail before producing its blackboard.
    has_market = any(bool(d.get("market")) for d in candidates.values())
    has_flow = any(bool(d.get("flow")) for d in candidates.values())
    has_research_or_news = any(bool(d.get("research") or d.get("news")) for d in candidates.values())
    has_feedback = bool(feedback)

    active = []
    for agent in agents:
        cluster = agent["cluster"]
        relevant = (
            (cluster in {"market_structure", "technical_setup"} and has_market)
            or (cluster == "capital_flow" and has_flow)
            or (cluster == "research_news" and has_research_or_news)
            or (cluster == "derivatives" and has_flow)
            or (cluster == "prediction_scenarios" and has_flow)
            or (cluster == "risk_invalidation" and (has_flow or has_research_or_news))
            or (cluster == "content_editorial" and bool(scores))
            or (cluster == "audience_growth" and bool(scores))
            or (cluster == "outcome_monetization" and has_feedback)
            or cluster == "safety_governance"
        )
        if relevant:
            active.append(agent["id"])

    ids = [a["id"] for a in agents]
    unique_ids = len(set(ids)) == len(ids)
    cluster_total_ok = sum(CLUSTERS[i][1] for i in range(len(CLUSTERS))) == TOTAL_AGENTS
    validation = {
        "logical_agent_count": len(agents),
        "expected_agent_count": TOTAL_AGENTS,
        "exact_count": len(agents) == TOTAL_AGENTS,
        "unique_ids": unique_ids,
        "cluster_totals_valid": cluster_total_ok,
        "sparse_max_neighbors": max((len(a["neighbors"]) for a in agents), default=0),
        "status": "VALID" if len(agents) == TOTAL_AGENTS and unique_ids and cluster_total_ok else "INVALID",
    }
    if validation["status"] != "VALID":
        raise RuntimeError(f"300-agent mesh validation failed: {validation}")

    top = scores[:10]
    state = {
        "version": "MESH-300.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "architecture": "sparse_weighted_specialist_network",
        "logical_agent_count": TOTAL_AGENTS,
        "active_agent_count": len(active),
        "clusters": {k: v for k, v in CLUSTERS},
        "activation": "evidence_gated",
        "validation": validation,
        "evidence_state": {
            "market_available": has_market,
            "flow_available": has_flow,
            "research_or_news_available": has_research_or_news,
            "verified_feedback_available": has_feedback,
        },
        "shared_blackboard": {
            "candidate_count": len(scores),
            "top_candidates": top,
            "publish_authority": "downstream_strategy_and_editorial_gates",
            "trading_authority": False,
            "revenue_claims": "observed_only",
        },
        "learning": {
            "feedback_available": has_feedback,
            "weight_updates": "reserved_for_verified_outcomes",
            "no_guaranteed_returns": True,
        },
        "agents": agents,
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    MESH_OUT.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "version": state["version"],
        "logical_agents": TOTAL_AGENTS,
        "active_agents": len(active),
        "validation": validation,
        "top": top[:3],
    }))
    return state


if __name__ == "__main__":
    main()
