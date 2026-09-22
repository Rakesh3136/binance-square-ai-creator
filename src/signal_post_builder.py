"""Signal-first Square post builder.

Builds concise, human-readable conditional market maps from the repository's
frozen prediction contract and verified Binance market-flow evidence. No new
facts, levels, outcomes, or revenue claims are invented here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "data/live/capital_flow_intelligence.json"
PROOF = ROOT / "data/live/public_prediction_proof.json"
PUB = ROOT / "analytics/publication_log.jsonl"


def load(path: Path, default: Any = None):
    if default is None:
        default = {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def symbol(value: Any) -> str:
    raw = str(value or "").upper().replace("BINANCE:", "").replace("$", "").strip()
    return raw[:-4] if raw.endswith("USDT") else raw


def fmt(value: Any) -> str:
    n = num(value)
    if n is None:
        return "n/a"
    return f"{n:.8g}"


def setup_from(selected: dict) -> dict:
    prediction = selected.get("prediction") if isinstance(selected.get("prediction"), dict) else {}
    setup = selected.get("trade_setup") if isinstance(selected.get("trade_setup"), dict) else {}
    direction = str(setup.get("side") or prediction.get("direction") or selected.get("direction") or "").upper()
    if direction == "SHORT_BIAS":
        direction = "SHORT"
    elif direction == "LONG_BIAS":
        direction = "LONG"
    entry = setup.get("trigger", prediction.get("entry_trigger", selected.get("entry_trigger")))
    tp1 = setup.get("tp1", prediction.get("tp1", selected.get("tp1")))
    tp2 = setup.get("tp2", prediction.get("tp2", selected.get("tp2")))
    sl = setup.get("invalidation", prediction.get("sl", selected.get("sl")))
    confidence = num(
        prediction.get("confidence"),
        num(selected.get("flow_confidence"), num(selected.get("confidence"))),
    )
    return {"direction": direction, "entry": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "confidence": confidence}


def complete(selected: dict) -> bool:
    s = setup_from(selected)
    try:
        e, a, b, stop = [float(s[k]) for k in ("entry", "tp1", "tp2", "sl")]
    except (TypeError, ValueError):
        return False
    level_ok = (
        stop < e < a <= b if s["direction"] == "LONG"
        else 0 < b <= a < e < stop if s["direction"] == "SHORT"
        else False
    )
    return s["direction"] in {"LONG", "SHORT"} and level_ok and (s["confidence"] or 0) >= 65


def flow_record(sym: str) -> dict:
    data = load(FLOW, {})
    for row in data.get("top_conditional_setups") or []:
        if symbol(row.get("symbol")) == sym:
            return row
    for row in (data.get("leaders") or []) + (data.get("laggards") or []):
        if symbol(row.get("symbol")) == sym:
            return row
    return {}


def recent_hooks() -> set[str]:
    if not PUB.exists():
        return set()
    found = set()
    try:
        for line in PUB.read_text(encoding="utf-8").splitlines()[-24:]:
            row = json.loads(line)
            hook = re.sub(r"[^a-z0-9 ]", "", str(row.get("hook") or "").lower()).strip()
            if hook:
                found.add(hook)
    except Exception:
        pass
    return found


def build_outcome_post(selected: dict | None = None) -> dict | None:
    proof = load(PROOF, {})
    if proof.get("status") != "VERIFIED_WIN_AVAILABLE" or proof.get("publishable") is not True:
        return None
    selected = selected if isinstance(selected, dict) else {}
    wanted, proven = symbol(selected.get("symbol")), symbol(proof.get("symbol"))
    if wanted and proven and wanted != proven:
        return None
    direction = str(proof.get("direction") or selected.get("direction") or "").upper()
    target, ref = proof.get("target"), proof.get("reference_price")
    ts, sym = str(proof.get("evaluated_at") or "").strip(), proven or wanted
    if not sym or not direction or target is None:
        return None
    hook = f"Verified follow-up: ${sym} {direction} call reached the frozen target."
    body = f"The original map used a frozen reference of {fmt(ref)} and target {fmt(target)}. Fresh Binance 1H candles later crossed that target."
    if ts:
        body += f" Outcome check: {ts}."
    close = f"That validates the historical setup only; it does not predict the next move. What should the next ${sym} confirmation test be?"
    return {"post": "\n\n".join([hook, body, close]), "hook": hook, "question": close, "style": "verified_outcome_followup", "symbol": sym, "outcome_proof": True}


def build_signal_post(selected: dict | None = None) -> dict | None:
    selected = selected if isinstance(selected, dict) else {}
    if not complete(selected):
        return None
    sym = symbol(selected.get("symbol"))
    s = setup_from(selected)
    if not sym:
        return None

    flow = flow_record(sym)
    ret6, ret12 = num(flow.get("return_6h_pct")), num(flow.get("return_12h_pct"))
    vr, pressure = num(flow.get("volume_ratio_6h_vs_prior_12h")), num(flow.get("volume_pressure_pct"))
    flow_score, quote = num(flow.get("flow_score")), num(flow.get("quote_volume_usdt"))

    facts = []
    if ret6 is not None:
        facts.append(f"6H {ret6:+.2f}%")
    if ret12 is not None:
        facts.append(f"12H {ret12:+.2f}%")
    if vr is not None:
        facts.append(f"volume {vr:.2f}x vs prior 12H")
    if pressure is not None:
        facts.append(f"pressure {pressure:+.3f}%")
    if flow_score is not None:
        facts.append(f"flow score {flow_score:+.2f}")
    if quote is not None and quote >= 1_000_000:
        facts.append(f"24H volume ${quote/1_000_000:.1f}M")
    facts = facts[:2]

    seed_material = f"{sym}|{s['direction']}|{s['entry']}|{s['sl']}"
    variant = int(hashlib.sha256(seed_material.encode()).hexdigest()[:8], 16) % 6
    recent = recent_hooks()

    hooks = [
        f"${sym} just reached the level I'm watching for a {s['direction'].lower()} setup.",
        f"Here's the part of ${sym} that matters now: does price accept the {s['direction'].lower()} trigger?",
        f"I'm not chasing ${sym}; the next 1H reaction around the trigger is the test.",
        f"${sym} is interesting here, but the setup only exists if price confirms it.",
        f"The ${sym} map is simple: trigger, confirmation, then targets — or invalidate it.",
        f"One level decides whether ${sym} stays on my {s['direction'].lower()} watchlist.",
    ]
    ordered = hooks[variant:] + hooks[:variant]

    def normalized(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()

    hook = next((x for x in ordered if normalized(x) not in recent), ordered[0])
    evidence_line = ", ".join(facts) + "." if facts else "The available evidence is enough to test the trigger, not enough to call it confirmed."
    why_variants = [
        f"The evidence is leaning {s['direction'].lower()} ({evidence_line})",
        f"The useful question isn't the headline; it's whether the move gets follow-through after the trigger. {evidence_line}",
        f"I'm treating the current candle as a setup, not confirmation. {evidence_line}",
        f"The 1H structure gives a conditional {s['direction'].lower()} map. {evidence_line}",
        f"Flow is supportive, but price still has to prove the idea. {evidence_line}",
        f"This is a reaction trade, not a prediction of certainty. {evidence_line}",
    ]
    why_now = why_variants[variant]
    plan = f"{s['direction']} trigger: {fmt(s['entry'])}  |  TP1 {fmt(s['tp1'])}  |  TP2 {fmt(s['tp2'])}  |  SL {fmt(s['sl'])}"
    condition = [
        "I want the trigger first; a clean retest is confirmation, not permission to chase.",
        "If price reclaims the invalidation level, I drop the idea — no forcing it.",
        "The trigger starts the test. Follow-through keeps it alive; invalidation ends it.",
        "No confirmation, no thesis. The market gets the final vote at the level.",
        "The risk boundary matters as much as the target; once it fails, the setup is finished.",
        "I'd rather miss the move than turn an unconfirmed candle into a certainty.",
    ][variant]
    questions = {
        "LONG": [
            f"Would you wait for a 1H hold above {fmt(s['entry'])} or the retest?",
            f"What would make you reject the LONG thesis around {fmt(s['entry'])}?",
            f"Breakout or retest — which would you trust more here?",
            f"Would volume confirmation change your view on this LONG?",
            f"Is the current move already too extended for you?",
            f"What would you need to see before calling this confirmed?",
        ],
        "SHORT": [
            f"Would you wait for a 1H break below {fmt(s['entry'])} or the retest?",
            f"What would make you reject the SHORT thesis around {fmt(s['entry'])}?",
            f"Breakdown or retest — which would you trust more here?",
            f"Would volume confirmation change your view on this SHORT?",
            f"Is the current move already too extended for you?",
            f"What would you need to see before calling this confirmed?",
        ],
    }[s["direction"]][variant]
    disclaimer = [
        "Conditional setup only; no guarantee.",
        "Scenario to test, not certainty.",
        "Conditional map; let price prove it.",
        "Setup only; outcome remains unknown.",
        "Risk boundary first; outcome unknown.",
        "Not a promise of outcome.",
    ][variant]

    post = "\n\n".join([hook, why_now, plan, condition, questions, disclaimer])
    return {
        "post": post,
        "hook": hook,
        "question": questions,
        "style": f"signal_map_mobile_human_v{variant + 1}",
        "symbol": sym,
        "signal_contract": s,
        "flow_evidence": facts,
    }
