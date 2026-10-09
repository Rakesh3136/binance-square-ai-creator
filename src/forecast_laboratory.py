#!/usr/bin/env python3
"""NIC Forecast Laboratory: evidence-scored competing hypotheses and outcome calibration.

Input JSON schema (top-level object):
  {"observations": [{"asset":"ABCUSDT", "timestamp":"ISO-8601", "return_pct":1.2,
    "volume_change_pct":8.0, "trend_score":0.4, "volatility_pct":2.1}],
   "outcomes": [{"asset":"ABCUSDT", "timestamp":"ISO-8601", "bull_probability":0.62,
    "bear_probability":0.38, "horizon_return_pct":3.0}]}

This module is a research aid, not a trading or publishing authorization. It never
changes safety gates and never claims that a probability guarantees an outcome.
Only past observations/outcomes relative to the current row should be supplied.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _num(row: dict, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return float(value)


def _regime(rows: list[dict]) -> dict:
    returns = [_num(row, "return_pct") for row in rows[-20:]]
    if len(returns) < 5:
        return {"label": "INSUFFICIENT_HISTORY", "observations": len(returns), "mean_return_pct": None, "volatility_pct": None}
    avg = mean(returns)
    vol = pstdev(returns)
    # Thresholds are descriptive heuristics, not learned or validated trading edges.
    if vol >= 3.0:
        label = "HIGH_VOLATILITY"
    elif avg >= 0.25:
        label = "POSITIVE_DRIFT"
    elif avg <= -0.25:
        label = "NEGATIVE_DRIFT"
    else:
        label = "RANGE_OR_MIXED"
    return {"label": label, "observations": len(returns), "mean_return_pct": round(avg, 4), "volatility_pct": round(vol, 4)}


def _brier(outcomes: list[dict]) -> dict:
    valid = []
    for row in outcomes:
        p = _num(row, "bull_probability")
        r = _num(row, "horizon_return_pct")
        if not 0 <= p <= 1:
            raise ValueError("bull_probability must be between 0 and 1")
        valid.append((p, 1.0 if r > 0 else 0.0))
    if not valid:
        return {"sample_count": 0, "bull_brier_score": None, "bull_hit_rate": None, "calibration_note": "No resolved historical forecasts; no calibration claim is possible."}
    score = mean((p - actual) ** 2 for p, actual in valid)
    return {"sample_count": len(valid), "bull_brier_score": round(score, 6), "bull_hit_rate": round(mean(actual for _, actual in valid), 4), "calibration_note": "Brier score is descriptive; compare against a baseline and use out-of-sample data before trusting it."}


def analyze(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("input must be a JSON object")
    observations = payload.get("observations", [])
    outcomes = payload.get("outcomes", [])
    if not isinstance(observations, list) or not isinstance(outcomes, list):
        raise ValueError("observations and outcomes must be arrays")
    clean = []
    for row in observations:
        if not isinstance(row, dict) or not row.get("asset"):
            raise ValueError("each observation must be an object with asset")
        item = dict(row)
        item["_dt"] = _time(row.get("timestamp"))
        for key in ("return_pct", "volume_change_pct", "trend_score", "volatility_pct"):
            _num(item, key)
        clean.append(item)
    clean.sort(key=lambda row: row["_dt"])
    by_asset = defaultdict(list)
    for row in clean:
        by_asset[str(row["asset"]).upper()].append(row)
    forecasts = []
    for asset, rows in sorted(by_asset.items()):
        current = rows[-1]
        hist = rows[:-1]
        regime = _regime(hist)
        ret = _num(current, "return_pct")
        volume = _num(current, "volume_change_pct")
        trend = _num(current, "trend_score")
        vol = _num(current, "volatility_pct")
        # Transparent, bounded heuristic scores. These are not trained probabilities.
        bull_raw = 0.45 * max(-1.0, min(1.0, trend)) + 0.25 * max(-1.0, min(1.0, ret / 3.0)) + 0.15 * max(-1.0, min(1.0, volume / 30.0)) - 0.15 * max(0.0, min(1.0, vol / 10.0))
        bull_score = max(0.0, min(1.0, 0.5 + bull_raw / 2.0))
        bear_score = 1.0 - bull_score
        extended = abs(ret) >= 5.0
        warnings = []
        if extended:
            warnings.append("LARGE_SINGLE_PERIOD_MOVE: avoid treating this as an early-entry signal")
        if regime["label"] == "INSUFFICIENT_HISTORY":
            warnings.append("INSUFFICIENT_HISTORY: regime estimate is unavailable")
        forecasts.append({"asset": asset, "as_of": current["timestamp"], "bull_hypothesis_score": round(bull_score, 4), "bear_hypothesis_score": round(bear_score, 4), "leading_hypothesis": "BULLISH" if bull_score > 0.55 else "BEARISH" if bull_score < 0.45 else "MIXED", "regime": regime, "latest_period_return_pct": round(ret, 4), "large_move_caution": extended, "warnings": warnings, "interpretation": "Heuristic research score, not a calibrated probability or trade instruction."})
    valid_outcomes = []
    for row in outcomes:
        if not isinstance(row, dict) or not row.get("asset"):
            raise ValueError("each outcome must be an object with asset")
        _time(row.get("timestamp"))
        valid_outcomes.append(row)
    return {"schema_version": 1, "engine": "NIC Forecast Laboratory", "status": "RESEARCH_ONLY", "forecast_count": len(forecasts), "forecasts": forecasts, "historical_calibration": _brier(valid_outcomes), "limitations": ["Scores are hand-weighted heuristics, not learned probabilities.", "Historical calibration is meaningful only when forecasts and outcomes are time-aligned and out-of-sample.", "No output overrides asset cooldown, extended-move, liquidity, fact-check, chart-validation, or publication gates.", "No profitability or future direction is guaranteed."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON input file")
    parser.add_argument("--output", default="data/reports/forecast-laboratory.json", help="Report output path")
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        report = analyze(payload)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": report["status"], "forecast_count": report["forecast_count"], "output": str(output), "calibration_samples": report["historical_calibration"]["sample_count"]}))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
