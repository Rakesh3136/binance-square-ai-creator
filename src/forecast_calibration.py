"""Calibration metrics for resolved, evidence-backed NIC directional forecasts.

This module scores forecast probabilities only when the result is explicitly
resolved. It does not infer outcomes from later prices and does not claim that
calibration alone establishes a profitable strategy.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

RESOLVED_RESULTS = {"up", "down"}
DEFAULT_BINS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))


def validate_forecast(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("forecast must be a JSON object")
    forecast_id = str(item.get("forecast_id") or "").strip()
    symbol = str(item.get("symbol") or "").strip().upper()
    result = str(item.get("resolved_direction") or "unresolved").strip().lower()
    evidence = item.get("resolution_evidence") or []
    probability = item.get("probability_up")
    if not forecast_id:
        raise ValueError("forecast_id is required")
    if not symbol:
        raise ValueError("symbol is required")
    if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability):
        raise ValueError("probability_up must be a finite number from 0 to 1")
    if not 0 <= probability <= 1:
        raise ValueError("probability_up must be between 0 and 1")
    if result not in RESOLVED_RESULTS | {"unresolved"}:
        raise ValueError("resolved_direction must be up, down, or unresolved")
    if not isinstance(evidence, list) or any(not str(x).strip() for x in evidence):
        raise ValueError("resolution_evidence must be a list of non-empty evidence references")
    if result != "unresolved" and not evidence:
        raise ValueError("resolved forecasts require resolution_evidence")
    return {
        "forecast_id": forecast_id,
        "symbol": symbol,
        "probability_up": float(probability),
        "resolved_direction": result,
        "resolution_evidence": [str(x).strip() for x in evidence],
        "horizon": str(item.get("horizon") or "").strip() or None,
        "strategy": str(item.get("strategy") or "").strip() or None,
    }


def calibration_report(forecasts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute Brier score and calibration bins from resolved forecasts only."""
    validated = [validate_forecast(item) for item in forecasts]
    seen: set[str] = set()
    for item in validated:
        if item["forecast_id"] in seen:
            raise ValueError(f"duplicate forecast_id: {item['forecast_id']}")
        seen.add(item["forecast_id"])

    resolved = [item for item in validated if item["resolved_direction"] in RESOLVED_RESULTS]
    unresolved_count = len(validated) - len(resolved)
    if not resolved:
        return {
            "forecast_count": len(validated),
            "resolved_count": 0,
            "unresolved_count": unresolved_count,
            "brier_score": None,
            "calibration_bins": [],
            "warning": "No resolved forecasts; no calibration score can be computed.",
        }

    rows = []
    squared_errors = []
    for item in resolved:
        observed = 1.0 if item["resolved_direction"] == "up" else 0.0
        p = item["probability_up"]
        squared_errors.append((p - observed) ** 2)
        rows.append((p, observed))

    bins = []
    for index, (lower, upper) in enumerate(DEFAULT_BINS):
        members = [(p, y) for p, y in rows
                   if lower <= p < upper or (index == len(DEFAULT_BINS) - 1 and p == 1.0)]
        if members:
            bins.append({
                "range": [lower, upper],
                "count": len(members),
                "mean_predicted_probability": sum(p for p, _ in members) / len(members),
                "observed_up_rate": sum(y for _, y in members) / len(members),
            })

    return {
        "forecast_count": len(validated),
        "resolved_count": len(resolved),
        "unresolved_count": unresolved_count,
        "brier_score": sum(squared_errors) / len(squared_errors),
        "calibration_bins": bins,
        "warning": "Lower Brier score is better for these resolved forecasts; it does not prove profitability, causality, or future performance. Compare only forecasts with compatible horizons and resolution rules.",
    }
