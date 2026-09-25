"""Hard validator for NIC's current-cycle prediction output."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTION = ROOT / "data" / "live" / "nic_prediction_engine.json"
OUT = ROOT / "data" / "live" / "nic_prediction_contract_validation.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(value, default=None):
    try:
        return float(value)
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
        terminal = num((row.get("walk_forward") or {}).get("terminal_samples"), 0)
        win_rate = num((row.get("walk_forward") or {}).get("win_rate"))
        setup = row.get("recommended_setup") if isinstance(row.get("recommended_setup"), dict) else {}
        state = str(setup.get("state") or "").upper()

        failures = []
        if not symbol:
            failures.append("missing_symbol")
        if side not in {"LONG", "SHORT"}:
            failures.append("invalid_side")
        if quality is None or quality < 72 or quality > 100:
            failures.append("quality_out_of_range")
        if calibrated is None or calibrated > 85:
            failures.append("confidence_ceiling_breached")
        if terminal < 25:
            failures.append("insufficient_terminal_samples")
        if win_rate is None or win_rate < 0.55:
            failures.append("historical_win_rate_below_threshold")
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
            errors.append({"symbol": symbol, "side": side, "failures": failures})
        else:
            validated_passes += 1

    result = {
        "version": "1.0-nic-prediction-contract",
        "validated_at": now.isoformat(),
        "candidate_count": len(candidates),
        "validated_passes": validated_passes,
        "errors": errors,
        "publishable_prediction_count": 0 if errors else validated_passes,
        "policy": [
            "A PASS must have a valid conditional setup.",
            "Minimum 25 post-fix terminal walk-forward samples are required.",
            "Minimum historical terminal win rate is 55%.",
            "NIC confidence is capped at 85 and is not a probability of profit.",
            "The setup must still be waiting for its trigger.",
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
