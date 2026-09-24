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
ACTIVITY = ROOT / "data/live/nic_activity.jsonl"
MACRO = ROOT / "data/live/global_macro_intelligence.json"
IMPACT = ROOT / "data/live/cross_asset_impact.json"
SELF_TRAINING = ROOT / "data/live/creator_self_training.json"
SELF_DEV = ROOT / "data/live/autonomous_self_development_gate.json"

def emit(event: str, stage: str, **details) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "status": "ACTIVE", "stage": stage, "event": event, **details}
    ACTIVITY.parent.mkdir(parents=True, exist_ok=True)
    with ACTIVITY.open("a", encoding="utf-8") as f: f.write(json.dumps(record, ensure_ascii=False) + "\\n")
    print(json.dumps(record, ensure_ascii=False))

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
    emit("NIC reading intelligence state", "observe")
    pre = load(ROOT / "data/live/editorial_preflight.json")
    routing = load(ROOT / "data/live/signal_first_routing.json")
    regime = load(ROOT / "data/live/market_regime.json")
    brain = load(ROOT / "data/live/creator_brain_decision.json")
    learning = load(ROOT / "data/live/creator_7_2_learning.json")
    audience = load(ROOT / "data/live/creator_22_0_audience_intelligence.json")
    macro = load(MACRO)
    impact = load(IMPACT)
    self_training = load(SELF_TRAINING)
    self_dev = load(SELF_DEV)
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
        "macro_available": bool(macro),
        "cross_asset_available": bool(impact),
        "self_training_available": bool(self_training),
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
    learned_patterns = self_training.get("policy", {}).get("observed_patterns", []) if isinstance(self_training.get("policy"), dict) else []
    hook_candidates = [p for p in learned_patterns if isinstance(p, dict) and p.get("dimension") == "hook_type" and int(p.get("samples", 0) or 0) >= 3]
    learned_hook = str(sorted(
        hook_candidates,
        key=lambda p: (float(p.get("avg_engagement_rate", 0) or 0), float(p.get("avg_views", 0) or 0)),
        reverse=True
    )[0].get("value") or "").lower() if hook_candidates else ""
    mapped = {"question": "decision", "breaking": "anomaly", "contrarian": "contradiction", "explanation": "mechanism", "fact_led": "anomaly"}
    if learned_hook in mapped:
        hook_family = mapped[learned_hook]
    else:
        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        family_index = int(hashlib.sha256((thesis_id + day_key).encode()).hexdigest()[:8], 16) % len(hook_families)
        hook_family = hook_families[family_index]

    plans = {
        "contradiction": f"${symbol} has a decision point where the obvious narrative can be tested against the verified market structure.",
        "mechanism": f"The useful story for ${symbol} is the measurable link between the observed move and the level that would confirm or reject it.",
        "decision": f"${symbol} becomes actionable only under the frozen condition; the point is the test, not a certainty about the outcome.",
        "anomaly": f"${symbol} is worth examining for the gap between what the headline suggests and what the supplied market evidence actually confirms.",
        "accountability": f"${symbol} should be evaluated against the same frozen setup after the market resolves it, so the Creator can learn from the result.",
    }
    emit("NIC completed evidence synthesis", "reason", symbol=symbol, evidence_score=evidence_score, hook_family=hook_family)
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
        "macro_context": {
            "primary_theme": macro.get("primary_theme"),
            "event_count": macro.get("event_count", 0),
            "cross_asset_watchlist": macro.get("cross_asset_watchlist", []),
            "impact_status": impact.get("status"),
        },
        "self_training": {
            "plan_id": self_training.get("plan_id"),
            "primary_variable": ((self_training.get("policy") or {}).get("next_experiment") or {}).get("primary_variable"),
            "underrepresented_lanes": (self_training.get("policy") or {}).get("underrepresented_lanes", []),
            "verified_revenue_observed": ((self_training.get("policy") or {}).get("verified_monetization") or {}).get("verified_revenue_observed", 0),
        },
        "self_development": {
            "run_self_engineer": bool(self_dev.get("run_self_engineer")),
            "reason": self_dev.get("reason"),
        },
        "external_models": "optional_advisors_only",
    }

def main() -> None:
    emit("NIC cycle started", "boot")
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
        "self_training_plan_id": state["self_training"]["plan_id"],
        "macro_theme": state["macro_context"]["primary_theme"],
        "external_models": "optional",
        "self_training": state["self_training"],
        "macro_context": state["macro_context"],
        "self_development": state["self_development"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    emit("NIC state persisted", "learn", thesis_id=state["thesis_id"], evidence_score=state["evidence_score"])
    print(json.dumps(state, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
