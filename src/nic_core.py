"""Keyless Neural Intelligence Core for Binance Square Creator.

NIC Core is the Creator's domain-specific reasoning layer. It does not call
Claude, Gemini, OpenAI, or any other hosted model. It operates on verified
snapshots and existing intelligence artifacts, producing a structured brief
that downstream writers may use.

This is intentionally not claimed to be a general-purpose frontier model.
Its advantage is domain specialization, determinism, auditability, memory and
failure recovery for this Creator.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/nic_core_state.json"
REPORT = ROOT / "data/intelligence/nic_core_report.json"

def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def symbol_of(d: dict) -> str:
    value = str(d.get("symbol") or d.get("base_asset") or "").upper()
    return re.sub(r"[^A-Z0-9]", "", value.replace("USDT", ""))

def build_state() -> dict:
    pre = load(ROOT / "data/live/editorial_preflight.json")
    routing = load(ROOT / "data/live/signal_first_routing.json")
    regime = load(ROOT / "data/live/market_regime.json")
    brain = load(ROOT / "data/live/creator_brain_decision.json")
    learning = load(ROOT / "data/live/creator_7_2_learning.json")
    audience = load(ROOT / "data/live/creator_22_0_audience_intelligence.json")
    selected = pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"), dict) else {}
    selected_signal = routing.get("selected") if isinstance(routing.get("selected"), dict) else {}

    source = selected_signal or selected
    symbol = symbol_of(source)
    contract = source.get("signal_contract") if isinstance(source.get("signal_contract"), dict) else {}
    direction = str(contract.get("direction") or source.get("direction") or "").upper()

    evidence_components = {
        "live_symbol_verified": bool(routing.get("live_symbol_verified") or source.get("live_symbol_verified")),
        "primary_signal": bool(routing.get("primary_signal")),
        "prediction_contract_complete": bool(routing.get("prediction_contract_complete") or source.get("prediction_contract_complete")),
        "binance_data_verified": bool(source.get("binance_data_verified") or routing.get("binance_data_verified")),
        "creator_brain_publish": bool(brain.get("publish") or brain.get("decision") in {"PUBLISH", "PASS"}),
        "regime_available": bool(regime),
        "learning_available": bool(learning),
        "audience_available": bool(audience),
    }
    evidence_score = round(100 * sum(evidence_components.values()) / max(1, len(evidence_components)), 1)

    thesis_seed = json.dumps({
        "symbol": symbol,
        "direction": direction,
        "contract": contract,
        "regime": regime.get("regime"),
        "brain": brain.get("decision"),
        "learning": learning.get("strategy_recommendations") or learning.get("recommendations"),
    }, sort_keys=True, ensure_ascii=False)
    thesis_id = hashlib.sha256(thesis_seed.encode()).hexdigest()[:16]

    hook_families = ["contradiction", "mechanism", "decision", "anomaly", "accountability"]
    day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    family_index = int(hashlib.sha256((thesis_id + day_key).encode()).hexdigest()[:8], 16) % len(hook_families)
    hook_family = hook_families[family_index]

    plans = {
        "contradiction": f"\${symbol} has a decision point where the obvious narrative can be tested against the verified market structure.",
        "mechanism": f"The useful story for \${symbol} is the measurable link between the observed move and the level that would confirm or reject it.",
        "decision": f"\${symbol} becomes actionable only under the frozen condition; the point is the test, not a certainty about the outcome.",
        "anomaly": f"\${symbol} is worth examining for the gap between what the headline suggests and what the supplied market evidence actually confirms.",
        "accountability": f"\${symbol} should be evaluated against the same frozen setup after the market resolves it, so the Creator can learn from the result.",
    }
    return {
        "nic_version": "1.0-keyless-domain-core",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thesis_id": thesis_id,
        "symbol": symbol,
        "direction": direction,
        "hook_family": hook_family,
        "evidence_score": evidence_score,
        "evidence_components": evidence_components,
        "frozen_contract": contract,
        "reasoning_principles": [
            "facts before narrative",
            "mechanism before hype",
            "conditional predictions",
            "one clear failure condition",
            "learn from resolved outcomes",
            "do not infer revenue from engagement",
        ],
        "editorial_thesis": plans[hook_family],
        "external_models": "optional_advisors_only",
    }

def main() -> None:
    state = build_state()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(json.dumps({
        "status": "READY",
        "nic_version": state["nic_version"],
        "thesis_id": state["thesis_id"],
        "evidence_score": state["evidence_score"],
        "hook_family": state["hook_family"],
        "external_models": "optional",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
