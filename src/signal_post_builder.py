"""Signal-first Square post builder.

Builds human-readable conditional market maps from the repository's frozen
prediction contract and verified Binance market-flow evidence. No new facts,
levels, outcomes, or revenue claims are invented here.
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
    entry = setup.get("trigger", prediction.get("entry_trigger", selected.get("entry_trigger")))
    tp1 = setup.get("tp1", prediction.get("tp1", selected.get("tp1")))
    tp2 = setup.get("tp2", prediction.get("tp2", selected.get("tp2")))
    sl = setup.get("invalidation", prediction.get("sl", selected.get("sl")))
    confidence = num(
        prediction.get("confidence"),
        num(selected.get("flow_confidence"), num(selected.get("confidence"))),
    )
    return {
        "direction": direction,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "confidence": confidence,
    }


def complete(selected: dict) -> bool:
    s = setup_from(selected)
    try:
        e, a, b, stop = [float(s[k]) for k in ('entry', 'tp1', 'tp2', 'sl')]
    except (TypeError, ValueError):
        return False
    level_ok = (
        stop < e < a <= b
        if s['direction'] == 'LONG'
        else 0 < b <= a < e < stop
        if s['direction'] == 'SHORT'
        else False
    )
    return s['direction'] in {'LONG', 'SHORT'} and level_ok and (s['confidence'] or 0) >= 65
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
    wanted = symbol(selected.get("symbol"))
    proven = symbol(proof.get("symbol"))
    if wanted and proven and wanted != proven:
        return None

    direction = str(proof.get("direction") or selected.get("direction") or "").upper()
    target = proof.get("target")
    ref = proof.get("reference_price")
    ts = str(proof.get("evaluated_at") or "").strip()
    sym = proven or wanted
    if not sym or not direction or target is None:
        return None

    hook = f"Verified follow-up: ${sym} {direction} call reached the frozen target."
    body = (
        f"The original map was built around ${sym} with a frozen reference of {fmt(ref)} "
        f"and target {fmt(target)}. Fresh Binance 1H candles later crossed that target."
    )
    if ts:
        body += f" Outcome check: {ts}."
    close = (
        "That result validates the historical setup only; it does not predict the next move. "
        f"What should the next ${sym} confirmation test be?"
    )
    return {
        "post": "\n\n".join([hook, body, close]),
        "hook": hook,
        "question": close,
        "style": "verified_outcome_followup",
        "symbol": sym,
        "outcome_proof": True,
    }


def build_signal_post(selected: dict | None = None) -> dict | None:
    selected = selected if isinstance(selected, dict) else {}
    if not complete(selected):
        return None

    sym = symbol(selected.get("symbol"))
    s = setup_from(selected)
    if not sym:
        return None

    flow = flow_record(sym)
    ret6 = num(flow.get("return_6h_pct"))
    ret12 = num(flow.get("return_12h_pct"))
    vr = num(flow.get("volume_ratio_6h_vs_prior_12h"))
    pressure = num(flow.get("volume_pressure_pct"))
    flow_score = num(flow.get("flow_score"))
    quote = num(flow.get("quote_volume_usdt"))

    facts = []
    if ret6 is not None:
        facts.append(f"6H return: {ret6:+.2f}%")
    if ret12 is not None:
        facts.append(f"12H return: {ret12:+.2f}%")
    if vr is not None:
        facts.append(f"6H volume vs prior 12H: {vr:.2f}x")
    if pressure is not None:
        facts.append(f"volume-weighted pressure: {pressure:+.3f}%")
    if flow_score is not None:
        facts.append(f"flow score: {flow_score:+.2f}")
    if quote is not None and quote >= 1_000_000:
        facts.append(f"24H quote volume: ${quote/1_000_000:.1f}M")
    facts = facts[:2]

    seed_material = f"{sym}|{s['direction']}|{s['entry']}|{s['sl']}"
    variant = int(hashlib.sha256(seed_material.encode()).hexdigest()[:8], 16) % 5
    recent = recent_hooks()

    hooks = [
        f'${sym} is at a level where the next 1H close matters more than the headline.',
        f"I'm watching ${sym} for one thing: whether sellers can actually keep price below the trigger." if s['direction'] == 'SHORT' else f"I'm watching ${sym} for one thing: whether buyers can actually keep price above the trigger.",
        f'${sym} looks interesting here, but the short only makes sense after the level gives way.' if s['direction'] == 'SHORT' else f'${sym} looks interesting here, but the long only makes sense after the level holds.',
        f'The ${sym} setup is pretty simple: trigger, retest, or invalidate.',
        f'This is a ${sym} test, not a chase; the trigger decides whether the thesis has legs.',
    ]
    ordered = hooks[variant:] + hooks[:variant]
    def has_recent_sentence(text: str) -> bool:
        for sentence in re.split(r"[.!?]+", text):
            normalized = re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip()
            if len(normalized.split()) >= 6 and normalized in recent:
                return True
        return False

    hook = next((x for x in ordered if not has_recent_sentence(x)), ordered[0])

    why_now_variants = [
        f"The flow read and 1H structure are leaning {s['direction']}. " + (', '.join(facts) + '.' if facts else 'That is enough evidence to test the trigger, not enough to call it confirmed.'),
        f'The evidence is aligned enough to test ${sym}, but the level still has to break or hold before the setup is valid.' + ((' ' + ', '.join(facts) + '.') if facts else ''),
        f'For ${sym}, the useful question is whether the move gets follow-through after the trigger.' + ((' ' + ', '.join(facts) + '.') if facts else ''),
        f"I'm not treating the current candle as confirmation on ${sym}. The next 1H reaction around the trigger is the real test." + ((' ' + ', '.join(facts) + '.') if facts else ''),
        f'The current structure gives ${sym} a conditional {s["direction"]} map; the market still has to prove it.' + ((' ' + ', '.join(facts) + '.') if facts else ''),
    ]
    why_now = why_now_variants[variant]

    condition_variants = [
        "I'd treat the first break as a trigger, not proof; the hold or retest is what makes the idea interesting.",
        "No confirmation, no thesis. If price reclaims the invalidation level, I'm done with the setup.",
        "Let price prove it at the trigger. A clean rejection back through invalidation kills the idea.",
        "The trigger starts the test; acceptance keeps it alive, while invalidation shuts it down.",
        "The market gets the final say here: trigger first, then confirmation, then targets.",
    ]
    condition = condition_variants[variant]
    plan = (
        f"Entry trigger: {fmt(s['entry'])}. "
        f"TP1: {fmt(s['tp1'])}. "
        f"TP2: {fmt(s['tp2'])}. "
        f"SL / invalidation: {fmt(s['sl'])}."
    )
    angle = [
        "I care more about what price does after the break than whether it tags the level for a second.",
        "There is no need to force it; a clean invalidation keeps the call honest.",
        "The useful part is the risk boundary: if that level fails, the idea is finished.",
        "Flow is still a proxy, so the 1H price action gets the final vote.",
        "No need to chase the candle. The trigger is the decision point.",
    ][variant]
    question = {
        "LONG": [
            f"Would you take a clean 1H hold above {fmt(s['entry'])}, or wait for the retest?",
            f"What would make you reject the LONG thesis around {fmt(s['entry'])}?",
            f"Do you want the breakout or the retest around {fmt(s['entry'])}?",
            f"Which matters more here: volume confirmation or the 1H close above {fmt(s['entry'])}?",
            f"Would you wait for the trigger, or is the current move already too extended?",
        ],
        "SHORT": [
            f"Would you take a clean 1H break below {fmt(s['entry'])}, or wait for the retest?",
            f"What would make you reject the SHORT thesis around {fmt(s['entry'])}?",
            f"Do you want the breakdown or the retest around {fmt(s['entry'])}?",
            f"Which matters more here: volume confirmation or the 1H close below {fmt(s['entry'])}?",
            f"Would you wait for the trigger, or is the move already too extended?",
        ],
    }[s["direction"]][variant]
    disclaimers = [
        'Conditional setup only; no guarantee.',
        'Scenario to test, not certainty.',
        'Conditional map; let price prove it.',
        'This is a setup to test, not a promised outcome.',
        'Risk boundary first; outcome unknown.',
    ]
    disclaimer = disclaimers[variant]
    return_payload = {
        "post": "\n\n".join([hook, why_now, condition, plan, angle, question, disclaimer]),
        "hook": hook,
        "question": question,
        "style": f"signal_map_variant_{variant + 1}_human",
        "symbol": sym,
        "signal_contract": s,
        "flow_evidence": facts,
    }

    return return_payload
