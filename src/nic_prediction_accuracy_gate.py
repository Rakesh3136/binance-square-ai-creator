"""Conservative second-pass accuracy gate for NIC predictions.

This does not manufacture confidence. It removes candidates whose historical
conditional setup evidence is too weak or too uncertain to publish.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
ENGINE = LIVE / "nic_prediction_engine.json"
OUT = LIVE / "nic_prediction_accuracy_gate.json"
REPORT = ROOT / "data" / "intelligence" / "nic_prediction_accuracy_gate_report.json"

MIN_TERMINAL = 40
MIN_WIN_RATE = 0.60
MIN_WILSON_LOWER = 0.52
MIN_ALIGNMENT = 0.75
MAX_AMBIGUOUS_RATE = 0.10
MAX_CURRENT_ATR_PCT = 8.0


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def wilson_lower(wins: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = wins / total
    denom = 1.0 + z * z / total
    centre = p + z * z / (2.0 * total)
    spread = z * math.sqrt((p * (1.0 - p) / total) + (z * z / (4.0 * total * total)))
    return (centre - spread) / denom


def evaluate(item: dict) -> tuple[bool, list[str], dict]:
    wf = item.get("walk_forward") if isinstance(item.get("walk_forward"), dict) else {}
    total = int(wf.get("terminal_samples") or 0)
    wins = int(wf.get("wins") or 0)
    losses = int(wf.get("losses") or 0)
    ambiguous = int(wf.get("ambiguous") or 0)
    win_rate = float(wf.get("win_rate") or 0.0)
    alignment = float(item.get("current_alignment") or 0.0)
    atr_values = []
    for frame in (item.get("current_timeframes") or {}).values():
        if isinstance(frame, dict) and frame.get("atr_pct") is not None:
            try:
                atr_values.append(float(frame["atr_pct"]))
            except (TypeError, ValueError):
                pass
    max_atr = max(atr_values) if atr_values else 0.0
    ambiguous_rate = ambiguous / max(total, 1)
    lower = wilson_lower(wins, total)

    reasons = []
    if total < MIN_TERMINAL:
        reasons.append(f"insufficient_terminal_samples:{total}<{MIN_TERMINAL}")
    if win_rate < MIN_WIN_RATE:
        reasons.append(f"win_rate_below_{MIN_WIN_RATE:.2f}:{win_rate:.3f}")
    if lower < MIN_WILSON_LOWER:
        reasons.append(f"wilson_lower_below_{MIN_WILSON_LOWER:.2f}:{lower:.3f}")
    if alignment < MIN_ALIGNMENT:
        reasons.append(f"multi_timeframe_alignment_below_{MIN_ALIGNMENT:.2f}:{alignment:.3f}")
    if ambiguous_rate > MAX_AMBIGUOUS_RATE:
        reasons.append(f"ambiguous_rate_above_{MAX_AMBIGUOUS_RATE:.2f}:{ambiguous_rate:.3f}")
    if max_atr > MAX_CURRENT_ATR_PCT:
        reasons.append(f"current_volatility_above_{MAX_CURRENT_ATR_PCT:.1f}pct:{max_atr:.2f}")
    if str(item.get("status") or "").upper() != "PASS":
        reasons.append("NIC_engine_status_not_PASS")
    setup = item.get("recommended_setup") if isinstance(item.get("recommended_setup"), dict) else {}
    if str(setup.get("state") or "").upper() != "AWAITING_TRIGGER":
        reasons.append("conditional_setup_not_awaiting_trigger")

    passed = not reasons
    metrics = {
        "terminal_samples": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "wilson_lower_95": round(lower, 4),
        "current_alignment": alignment,
        "ambiguous_rate": round(ambiguous_rate, 4),
        "max_current_atr_pct": max_atr,
    }
    return passed, reasons, metrics


def main() -> int:
    engine = load(ENGINE)
    candidates = engine.get("candidates") or []
    passes = []
    waits = []
    audit = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        passed, reasons, metrics = evaluate(item)
        row = {
            "symbol": item.get("symbol"),
            "side": item.get("side"),
            "passed": passed,
            "reasons": reasons,
            "metrics": metrics,
        }
        audit.append(row)
        updated = dict(item)
        updated["accuracy_gate"] = metrics
        updated["accuracy_gate_pass"] = passed
        if passed:
            # Confidence is deliberately based on the conservative confidence
            # bound, not the raw quality score.
            updated["calibrated_confidence"] = round(min(85.0, max(52.0, metrics["wilson_lower_95"] * 100.0)), 2)
            passes.append(updated)
        else:
            updated["status"] = "WAIT"
            updated["reasons"] = list(dict.fromkeys(list(updated.get("reasons") or []) + reasons))
            waits.append(updated)

    result = {
        "version": "1.0-conservative-accuracy-gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY",
        "policy": {
            "min_terminal_samples": MIN_TERMINAL,
            "min_win_rate": MIN_WIN_RATE,
            "min_wilson_lower_95": MIN_WILSON_LOWER,
            "min_current_alignment": MIN_ALIGNMENT,
            "max_ambiguous_rate": MAX_AMBIGUOUS_RATE,
            "max_current_atr_pct": MAX_CURRENT_ATR_PCT,
            "no_confidence_boost_from_raw_quality": True,
            "weak_evidence_means_wait": True,
        },
        "candidates": passes + waits,
        "selected_passes": passes,
        "selected_waits": waits,
        "audit": audit,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "version": result["version"],
        "generated_at": result["generated_at"],
        "passes": len(passes),
        "waits": len(waits),
        "policy": result["policy"],
        "audit": audit,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "READY", "passes": len(passes), "waits": len(waits), "audit": audit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
