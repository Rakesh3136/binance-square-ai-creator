"""Bounded multi-agent supervisor for the autonomous creator.

This is a decision-support layer, not a second publisher. It synthesizes the
already-collected evidence into one compact strategy artifact consumed by the
editorial director. Agents never receive posting credentials and deterministic
gates remain authoritative.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/creator_agent_supervisor.json"
STRATEGY = ROOT / "data/live/agent_strategy.json"


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


def main() -> None:
    cadence = load("data/live/autonomous_cadence_6.json")
    frozen = load("data/live/frozen_opportunity.json")
    contract = load("data/live/opportunity_contract.json")
    context = load("data/live/publication_context.json")
    preflight = load("data/live/editorial_preflight.json")
    flow = load("data/live/capital_flow_intelligence.json")
    learning = load("data/intelligence/learning.json")
    performance = load("analytics/square_performance_state.json")

    selected = preflight.get("selected_opportunity") or {}
    story = preflight.get("content_director_4", {}).get("primary_story") or {}
    symbol = clean_symbol(first(
        frozen.get("symbol_usdt"), frozen.get("symbol"), contract.get("symbol"),
        selected.get("symbol"), context.get("symbol"), story.get("symbol")
    ))
    category = str(first(
        contract.get("category"), frozen.get("category"), selected.get("category"),
        context.get("category"), story.get("lane")
    ) or "").lower()
    publish = bool(cadence.get("publish", False))

    rotation = flow.get("market_rotation") or {}
    regime = rotation.get("market_regime") or "unknown"
    leaders = rotation.get("leaders") or []
    laggards = rotation.get("laggards") or []
    trade_setup = selected.get("trade_setup") or {}

    # The agents are bounded roles over existing evidence. Their output is a
    # compact strategy contract, not free-form AI text.
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
    if publish and symbol in {"BTC", "ETH"} and str(frozen.get("fallback_policy", "")).startswith("NEVER_FALLBACK"):
        # BTC/ETH are allowed when genuinely selected; this only records that
        # fallback protection is active rather than blocking legitimate stories.
        pass

    decision = "PROCEED_TO_EXISTING_GATES" if publish and not blockers else "WAIT"
    performance_health = {
        "feed_records": int(performance.get("feed_records", 0) or 0),
        "matched_post_ids": int(performance.get("matched_post_ids", 0) or 0),
        "collector_version": performance.get("collector_version"),
        "blind": int(performance.get("feed_records", 0) or 0) == 0,
    }
    strategy = {
        "version": "1.1-agent-strategy-contract",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "category": category,
        "thesis": thesis,
        "archetype": archetype,
        "market_regime": regime,
        "leaders": leaders[:5],
        "laggards": laggards[:5],
        "trade_setup": trade_setup,
        "story": story,
        "one_authoring_pass": True,
        "evidence_only": True,
        "performance_health": performance_health,
        "do_not_publish_if": blockers,
    }
    STRATEGY.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "version": "1.1-bounded-agent-supervisor",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "publish_intent": publish,
        "authoritative_symbol": symbol,
        "authoritative_category": category,
        "blockers": blockers,
        "agents": {
            "research": {"status": "READY", "role": "verify market/news/flow evidence", "authority": "evidence"},
            "strategy": {"status": "READY" if symbol else "BLOCKED", "role": "select one differentiated thesis", "authority": "frozen_opportunity"},
            "editorial": {"status": "READY" if publish else "WAIT", "role": "shape one human-style authoring pass", "authority": "editorial_gates"},
            "outcome": {"status": "READY", "role": "bind prior calls to outcomes and lessons", "authority": "performance_ledger"},
            "revenue": {"status": "OBSERVE_ONLY", "role": "measure eligible reader-intent signals", "authority": "analytics"},
            "safety": {"status": "READY", "role": "prevent manipulation, spam, duplication and unsupported claims", "authority": "deterministic_gates"},
        },
        "strategy_artifact": str(STRATEGY.relative_to(ROOT)),
        "performance_health": performance_health,
        "policy": {
            "single_authoritative_asset": True,
            "one_authoring_pass": True,
            "agents_cannot_publish": True,
            "agents_cannot_merge": True,
            "deterministic_gates_win": True,
            "wait_is_valid": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"decision": decision, "symbol": symbol, "category": category, "thesis": thesis, "performance_blind": performance_health["blind"]}))


if __name__ == "__main__":
    main()
