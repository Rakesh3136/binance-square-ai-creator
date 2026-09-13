"""Bounded multi-agent supervisor for the autonomous creator.

Agents are represented as deterministic roles over existing evidence files. They do
not receive Binance publishing credentials and cannot publish, merge, or change
workflow permissions. The supervisor produces one compact decision artifact for
the existing pipeline; deterministic gates remain authoritative.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/creator_agent_supervisor.json"


def load(path: str) -> dict:
    p = ROOT / path
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def first(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def main() -> None:
    cadence = load("data/live/autonomous_cadence_6.json")
    frozen = load("data/live/frozen_opportunity.json")
    contract = load("data/live/opportunity_contract.json")
    context = load("data/live/publication_context.json")
    control = load("data/live/creator_control_plane.json")
    learning = load("data/intelligence/learning.json")

    symbol = first(frozen.get("symbol_usdt"), frozen.get("symbol"), contract.get("symbol"), context.get("symbol"))
    category = first(contract.get("category"), frozen.get("category"), context.get("category"))
    publish = bool(cadence.get("publish", False))

    agents = {
        "research": {"status": "READY", "role": "verify market/news/flow evidence", "authority": "evidence"},
        "strategy": {"status": "READY" if symbol else "BLOCKED", "role": "select one differentiated thesis", "authority": "frozen_opportunity"},
        "editorial": {"status": "READY" if publish else "WAIT", "role": "shape human-style content without inventing facts", "authority": "editorial_gates"},
        "outcome": {"status": "READY", "role": "bind prior calls to outcomes and lessons", "authority": "performance_ledger"},
        "revenue": {"status": "OBSERVE_ONLY", "role": "measure eligible reader-intent signals", "authority": "analytics"},
        "safety": {"status": "READY", "role": "prevent manipulation, spam, duplication and unsupported claims", "authority": "deterministic_gates"},
    }

    blockers = []
    if publish and not symbol:
        blockers.append("missing_authoritative_asset")
    if publish and not category:
        blockers.append("missing_opportunity_category")
    if publish and not contract:
        blockers.append("missing_opportunity_contract")

    decision = "PROCEED_TO_EXISTING_GATES" if publish and not blockers else "WAIT"
    result = {
        "version": "1.0-bounded-agent-supervisor",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "publish_intent": publish,
        "authoritative_symbol": symbol,
        "authoritative_category": category,
        "blockers": blockers,
        "agents": agents,
        "control_plane_present": bool(control),
        "learning_present": bool(learning),
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
    print(json.dumps({"decision": decision, "symbol": symbol, "category": category, "blockers": blockers}))


if __name__ == "__main__":
    main()
