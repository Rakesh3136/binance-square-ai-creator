"""Bounded multi-agent supervisor for the autonomous creator.

This is a decision-support layer, not a second publisher. It synthesizes the
already-collected evidence into one compact strategy artifact consumed by the
editorial director. Agents never receive posting credentials and deterministic
gates remain authoritative.
"""
from __future__ import annotations
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/creator_agent_supervisor.json"
STRATEGY = ROOT / "data/live/agent_strategy.json"
MESH = ROOT / "data/live/agent_mesh_300.json"


def load(path: str) -> dict:
    p = ROOT / path
    try:
        value = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def first(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def clean_symbol(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper().replace("USDT", ""))


def run_300_agent_mesh() -> dict:
    """Run and validate the 300 logical specialist network for this cycle."""
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from agent_mesh_300 import main as mesh_main

        mesh = mesh_main()
    except Exception as exc:
        raise RuntimeError(f"300-agent mesh failed: {exc}") from exc

    agents = mesh.get("agents") or []
    ids = [a.get("id") for a in agents if isinstance(a, dict)]
    if (
        mesh.get("logical_agent_count") != 300
        or len(agents) != 300
        or len(ids) != 300
        or len(set(ids)) != 300
    ):
        raise RuntimeError("300-agent mesh validation failed: expected 300 unique logical agents")
    return mesh


def main() -> None:
    cadence = load("data/live/autonomous_cadence_6.json")
    frozen = load("data/live/frozen_opportunity.json")
    authoritative = load("data/live/authoritative_opportunity.json")
    contract = load("data/live/opportunity_contract.json")
    context = load("data/live/publication_context.json")
    preflight = load("data/live/editorial_preflight.json")
    flow = load("data/live/capital_flow_intelligence.json")
    learning = load("data/intelligence/learning.json")
    performance = load("analytics/square_performance_state.json")

    # Run the logical 300-agent network only after the fresh market, flow, news,
    # and research layers have populated the blackboard. It can enrich strategy,
    # but publication authority remains downstream and deterministic.
    mesh = run_300_agent_mesh()
    top_candidates = ((mesh.get("shared_blackboard") or {}).get("top_candidates") or [])

    selected = preflight.get("selected_opportunity") or {}
    selected = selected if isinstance(selected, dict) else {}
    story = preflight.get("content_director_4", {}).get("primary_story") or {}
    story = story if isinstance(story, dict) else {}

    # publication_context is the authoritative identity at authoring time. The
    # supervisor also runs earlier in the workflow, so frozen/portfolio state
    # may legitimately be stale until the publish branch freezes a new asset.
    # Prefer the current publication context, then the frozen/authoritative
    # opportunity, and only then preflight. This prevents the strategy artifact
    # from becoming the source of an asset-drift failure downstream.
    symbol = clean_symbol(first(
        context.get("symbol"), authoritative.get("symbol"), frozen.get("symbol_usdt"),
        frozen.get("symbol"), contract.get("symbol"), selected.get("symbol"), story.get("symbol")
    ))

    category = str(first(
        context.get("category"), authoritative.get("category"), frozen.get("category"),
        contract.get("category"), selected.get("category"), story.get("lane")
    ) or "").lower()
    publish = bool(cadence.get("publish", False))

    rotation = flow.get("market_rotation") or {}
    regime = rotation.get("market_regime") or "unknown"
    leaders = rotation.get("leaders") or []
    laggards = rotation.get("laggards") or []

    mesh_consensus = {}
    for candidate in top_candidates:
        if isinstance(candidate, dict) and clean_symbol(candidate.get("symbol")) == symbol:
            mesh_consensus = candidate
            break

    selected_symbol = clean_symbol(selected.get("symbol"))
    context_symbol = clean_symbol(context.get("symbol"))
    selected_matches = not selected_symbol or not context_symbol or selected_symbol == context_symbol
    trade_setup = selected.get("trade_setup") or {} if selected_matches else {}
    if not isinstance(trade_setup, dict):
        trade_setup = {}
    if not trade_setup:
        for x in flow.get("top_conditional_setups") or []:
            if not isinstance(x, dict):
                continue
            if clean_symbol(x.get("symbol")) == symbol:
                trade_setup = x.get("trade_setup") or x.get("prediction") or {}
                if not isinstance(trade_setup, dict):
                    trade_setup = {}
                break

    if category in {"capital_flow_long", "capital_flow_short"}:
        thesis = "capital-flow setup: regime + relative strength + participation must agree"
        archetype = "flow_trader"
    elif category in {"top_gainers", "top_losers", "high_volatility"}:
        thesis = "momentum discovery: the reaction after the impulse is the confirmation test"
        archetype = "high_energy"
    elif category in {"breaking_news", "news_and_macro", "news"}:
        thesis = "event impact: separate the verified event from the market response"
        archetype = "newsroom"
    elif category == "technical_setup":
        thesis = "technical decision point: supplied level and reaction determine the read"
        archetype = "technical_analyst"
    elif category in {"research_radar", "watchlist", "new_listings"}:
        thesis = "research anomaly: explain what is known, what is missing, and what would confirm it"
        archetype = "research_analyst"
    elif category == "crypto_meme":
        thesis = "crypto-native meme: humor anchored to one supplied market fact"
        archetype = "meme_creator"
    else:
        thesis = "evidence-led market story: one concrete observation followed by a testable interpretation"
        archetype = "conversational"

    blockers = []
    if publish and not symbol:
        blockers.append("missing_authoritative_asset")
    if publish and not category:
        blockers.append("missing_opportunity_category")
    if publish and not contract:
        blockers.append("missing_opportunity_contract")

    decision = "PROCEED_TO_EXISTING_GATES" if publish and not blockers else "WAIT"
    performance_health = {
        "feed_records": int(performance.get("feed_records", 0) or 0),
        "matched_post_ids": int(performance.get("matched_post_ids", 0) or 0),
        "collector_version": performance.get("collector_version"),
        "blind": int(performance.get("feed_records", 0) or 0) == 0,
    }
    strategy = {
        "version": "1.3-300-agent-mesh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "category": category,
        "thesis": thesis,
        "archetype": archetype,
        "market_regime": regime,
        "leaders": leaders[:5],
        "laggards": laggards[:5],
        "trade_setup": trade_setup,
        "story": story if (not context_symbol or not story.get("symbol") or clean_symbol(story.get("symbol")) == symbol) else {},
        "one_authoring_pass": True,
        "evidence_only": True,
        "performance_health": performance_health,
        "authoritative_asset_source": "publication_context",
        "selected_asset_aligned": selected_matches,
        "do_not_publish_if": blockers,
        "agent_mesh": {
            "version": mesh.get("version"),
            "logical_agents": mesh.get("logical_agent_count", 300),
            "active_agents": mesh.get("active_agent_count", 0),
            "consensus": mesh_consensus,
            "publish_authority": "downstream_strategy_and_editorial_gates",
            "trading_authority": False,
            "revenue_observation_only": True,
        },
    }
    STRATEGY.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "version": "1.3-300-agent-mesh",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "publish_intent": publish,
        "authoritative_symbol": symbol,
        "authoritative_category": category,
        "blockers": blockers,
        "asset_alignment": {
            "publication_context": context_symbol,
            "selected_opportunity": selected_symbol,
            "aligned": selected_matches,
            "stale_selection_is_not_used_for_strategy": not selected_matches,
        },
        "agents": {
            "research": {"status": "READY", "role": "verify market/news/flow evidence", "authority": "evidence"},
            "strategy": {"status": "READY" if symbol else "BLOCKED", "role": "select one differentiated thesis", "authority": "publication_context"},
            "mesh": {"status": "READY", "role": "aggregate 300 sparse specialist signals", "authority": "evidence_only"},
            "editorial": {"status": "READY" if publish else "WAIT", "role": "shape one human-style authoring pass", "authority": "editorial_gates"},
            "outcome": {"status": "READY", "role": "bind prior calls to outcomes and lessons", "authority": "performance_ledger"},
            "revenue": {"status": "OBSERVE_ONLY", "role": "measure eligible reader-intent signals", "authority": "analytics"},
            "safety": {"status": "READY", "role": "prevent manipulation, spam, duplication and unsupported claims", "authority": "deterministic_gates"},
        },
        "strategy_artifact": str(STRATEGY.relative_to(ROOT)),
        "mesh_artifact": str(MESH.relative_to(ROOT)),
        "performance_health": performance_health,
        "policy": {
            "logical_agent_count": 300,
            "sparse_network": True,
            "single_authoritative_asset": True,
            "publication_context_wins": True,
            "one_authoring_pass": True,
            "agents_cannot_publish": True,
            "agents_cannot_trade": True,
            "deterministic_gates_win": True,
            "wait_is_valid": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "decision": decision,
        "symbol": symbol,
        "category": category,
        "thesis": thesis,
        "performance_blind": performance_health["blind"],
        "selected_asset_aligned": selected_matches,
        "mesh_version": mesh.get("version"),
        "logical_agents": 300,
        "active_agents": mesh.get("active_agent_count", 0),
        "mesh_consensus_found": bool(mesh_consensus),
    }))


if __name__ == "__main__":
    main()
