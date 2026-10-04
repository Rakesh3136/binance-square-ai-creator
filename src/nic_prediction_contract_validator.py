"""NIC 23 — evidence-backed trade prediction contract validator.

This gate does not claim certainty. It separates a model's confidence score from
statistical evidence about historical outcomes and refuses to treat small samples
as trading experience.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTION = ROOT / "data" / "live" / "nic_prediction_engine.json"
OUT = ROOT / "data" / "live" / "nic_prediction_contract_validation.json"

MIN_TERMINAL = 25
STRONG_TERMINAL = 50
MIN_WIN_RATE = 0.55
STRONG_WIN_RATE = 0.65
MIN_ONE_SIDED_90_LOWER = 0.50
STRONG_ONE_SIDED_90_LOWER = 0.55
MAX_MODEL_CONFIDENCE = 85.0


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def levels_valid(side, setup):
    try:
        entry = float(setup["trigger"])
        tp1 = float(setup["tp1"])
        tp2 = float(setup["tp2"])
        stop = float(setup["invalidation"])
    except (TypeError, ValueError, KeyError):
        return False
    if min(entry, tp1, tp2, stop) <= 0:
        return False
    return stop < entry < tp1 <= tp2 if side == "LONG" else 0 < tp2 <= tp1 < entry < stop


def wilson_lower_90(wins: int, samples: int) -> float | None:
    """One-sided 90% Wilson lower bound for a binomial success rate."""
    if samples <= 0 or wins < 0 or wins > samples:
        return None
    z = 1.2815515655446004
    p = wins / samples
    denom = 1.0 + z * z / samples
    centre = p + z * z / (2.0 * samples)
    spread = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * samples)) / samples)
    return max(0.0, (centre - spread) / denom)


def evidence_tier(terminal: int, win_rate: float | None, lower90: float | None) -> str:
    if terminal < MIN_TERMINAL or win_rate is None or lower90 is None:
        return "INSUFFICIENT_DATA"
    if terminal >= STRONG_TERMINAL and win_rate >= STRONG_WIN_RATE and lower90 >= STRONG_ONE_SIDED_90_LOWER:
        return "STRONG_EVIDENCE"
    if win_rate >= MIN_WIN_RATE and lower90 >= MIN_ONE_SIDED_90_LOWER:
        return "EVIDENCE_BACKED"
    return "WEAK_OR_UNPROVEN"


def main() -> int:
    doc = load(PREDICTION)
    candidates = doc.get("candidates") if isinstance(doc.get("candidates"), list) else []
    errors = []
    validated_passes = 0
    now = datetime.now(timezone.utc)

    for row in candidates:
        if not isinstance(row, dict):
            errors.append("non_object_candidate")
            continue
        if str(row.get("status") or "").upper() != "PASS":
            continue

        symbol = str(row.get("symbol") or "").upper()
        side = str(row.get("side") or "").upper()
        quality = num(row.get("quality_score"))
        calibrated = num(row.get("calibrated_confidence"))
        wf = row.get("walk_forward") if isinstance(row.get("walk_forward"), dict) else {}
        terminal = int(num(wf.get("terminal_samples"), 0) or 0)
        wins = int(num(wf.get("wins"), 0) or 0)
        losses = int(num(wf.get("losses"), 0) or 0)
        win_rate = num(wf.get("win_rate"))
        if wins + losses > 0:
            terminal = min(terminal, wins + losses) if terminal else wins + losses
            win_rate = wins / (wins + losses)
        lower90 = wilson_lower_90(wins, wins + losses) if wins + losses else None
        tier = evidence_tier(terminal, win_rate, lower90)
        setup = row.get("recommended_setup") if isinstance(row.get("recommended_setup"), dict) else {}
        state = str(setup.get("state") or "").upper()

        row["nic23_evidence"] = {
            "tier": tier,
            "terminal_samples": terminal,
            "wins": wins,
            "losses": losses,
            "empirical_win_rate": round(win_rate, 4) if win_rate is not None else None,
            "one_sided_90_percent_wilson_lower": round(lower90, 4) if lower90 is not None else None,
            "not_a_profit_guarantee": True,
        }

        failures = []
        if not symbol:
            failures.append("missing_symbol")
        if side not in {"LONG", "SHORT"}:
            failures.append("invalid_side")
        if quality is None or quality < 72 or quality > 100:
            failures.append("quality_out_of_range")
        if calibrated is None or calibrated > MAX_MODEL_CONFIDENCE:
            failures.append("confidence_ceiling_breached")
        if terminal < MIN_TERMINAL:
            failures.append("insufficient_terminal_samples")
        if win_rate is None or win_rate < MIN_WIN_RATE:
            failures.append("historical_win_rate_below_threshold")
        if lower90 is None or lower90 < MIN_ONE_SIDED_90_LOWER:
            failures.append("90_percent_statistical_lower_bound_below_50_percent")
        if state != "AWAITING_TRIGGER":
            failures.append("setup_not_waiting_for_trigger")
        if not levels_valid(side, setup):
            failures.append("invalid_setup_levels")

        latest = row.get("latest_completed_candle") if isinstance(row.get("latest_completed_candle"), dict) else {}
        close_time = latest.get("close_time")
        if close_time is None:
            failures.append("missing_latest_completed_candle_timestamp")
        else:
            try:
                candle_dt = datetime.fromtimestamp(int(close_time) / 1000, tz=timezone.utc)
                if candle_dt >= now:
                    failures.append("open_or_future_candle_used")
            except (TypeError, ValueError, OSError):
                failures.append("invalid_latest_completed_candle_timestamp")

        if failures:
            errors.append({"symbol": symbol, "side": side, "failures": failures, "evidence": row["nic23_evidence"]})
        else:
            validated_passes += 1

    result = {
        "version": "23.0-nic-trade-evidence-contract",
        "validated_at": now.isoformat(),
        "candidate_count": len(candidates),
        "validated_passes": validated_passes,
        "errors": errors,
        "publishable_prediction_count": 0 if errors else validated_passes,
        "policy": [
            "NIC never represents a trade as certain or guaranteed.",
            "Model confidence and historical success probability are separate quantities.",
            "Minimum 25 terminal walk-forward outcomes are required.",
            "Minimum empirical terminal win rate is 55%.",
            "A one-sided 90% Wilson lower bound must be at least 50%; this means the evidence is statistically compatible with a true success rate above 50%, not that the trade has a 90% chance of profit.",
            "Strong evidence requires at least 50 terminal outcomes, >=65% empirical win rate, and >=55% one-sided 90% Wilson lower bound.",
            "Model confidence remains capped at 85 and is never presented as a probability of profit.",
            "Open/future candles are never accepted as prediction evidence.",
            "This validator cannot override safety gates or create a setup.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
