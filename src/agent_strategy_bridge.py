"""Apply the bounded agent strategy to the existing editorial contract.

This bridge only adjusts editorial direction; it never changes the authoritative
asset, category, evidence, or publication decision.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data/live/editorial_preflight.json"
STRATEGY = ROOT / "data/live/agent_strategy.json"

STYLE_TO_NARRATIVE = {
    "flow_trader": "capital_flow",
    "high_energy": "momentum_question",
    "newsroom": "event_context_impact",
    "technical_analyst": "level_confirmation",
    "research_analyst": "research_radar",
    "meme_creator": "crypto_meme",
    "conversational": "what_to_watch",
}


def main():
    if not PREFLIGHT.exists() or not STRATEGY.exists():
        print("Agent strategy bridge: no strategy artifact; preserving existing contract")
        return
    try:
        pre = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
        strategy = json.loads(STRATEGY.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Agent strategy bridge: invalid artifact: {exc}")
    selected = pre.get("selected_opportunity") or {}
    authoritative = str(selected.get("symbol") or (pre.get("content_director_4") or {}).get("primary_story", {}).get("symbol") or "").upper().replace("USDT", "")
    agent_symbol = str(strategy.get("symbol") or "").upper().replace("USDT", "")
    if authoritative and agent_symbol and authoritative != agent_symbol:
        raise SystemExit(f"Agent strategy bridge: asset mismatch {authoritative} != {agent_symbol}")
    d = pre.setdefault("content_director_4", {})
    style = str(strategy.get("archetype") or "").strip()
    narrative = STYLE_TO_NARRATIVE.get(style)
    if narrative and str(selected.get("category") or "").lower() not in {"capital_flow_long", "capital_flow_short", "crypto_meme"}:
        d["narrative_engine"] = narrative
    d["agent_strategy_thesis"] = strategy.get("thesis")
    d["agent_archetype"] = style
    d["agent_one_authoring_pass"] = bool(strategy.get("one_authoring_pass", True))
    d["agent_evidence_only"] = bool(strategy.get("evidence_only", True))
    d["agent_strategy_version"] = strategy.get("version")
    PREFLIGHT.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status":"OK","symbol":authoritative,"archetype":style,"narrative":narrative,"one_authoring_pass":True}))


if __name__ == "__main__":
    main()
