"""NIC Forecast probability calibration joined to immutable snapshots and terminal events."""
from __future__ import annotations
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS = ROOT / "data/intelligence/nic_forecast_outcome_events.jsonl"
OUT = ROOT / "data/intelligence/nic_forecast_calibration.json"
H = (6, 12, 24)
MIN = 30


def load_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except (json.JSONDecodeError, TypeError):
            continue
    return rows


def read():
    """Join matured terminal outcome events to immutable forecast snapshots.

    Legacy snapshots already marked resolved remain readable. New event-ledger
    outcomes take precedence; unresolved snapshots never enter scoring.
    """
    snapshots = load_jsonl(LEDGER)
    events = load_jsonl(EVENTS)
    terminal = {}
    for event in events:
        fid = str(event.get("forecast_id") or "")
        if fid and event.get("event_type") == "FORECAST_RESOLVED":
            terminal[fid] = event

    rows = []
    seen = set()
    for snapshot in snapshots:
        fid = str(snapshot.get("forecast_id") or "")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        try:
            horizon = int(snapshot.get("horizon_hours") or 0)
        except (TypeError, ValueError):
            continue
        if horizon not in H:
            continue
        event = terminal.get(fid)
        if event is not None:
            try:
                signed = float(event["signed_return"])
                hit = bool(event["hit"]) if "hit" in event else signed > 0
            except (KeyError, TypeError, ValueError):
                continue
            row = dict(snapshot)
            row.update({"resolved": True, "signed_return": signed, "hit": hit,
                        "resolution_event_id": event.get("event_id")})
            rows.append(row)
        elif snapshot.get("resolved"):
            # Backward compatibility for snapshots resolved before event-ledger rollout.
            row = dict(snapshot)
            try:
                row["signed_return"] = float(row.get("signed_return") or 0.0)
            except (TypeError, ValueError):
                continue
            row["hit"] = bool(row.get("hit", row["signed_return"] > 0))
            rows.append(row)
    return rows


def clamp(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.5
    if not math.isfinite(x):
        return 0.5
    return max(0.0, min(1.0, x))


def metrics(rows):
    scored = [r for r in rows if r.get("forecast_probability") is not None]
    if not scored:
        return {"samples": 0, "brier_score": None, "log_loss": None, "coverage": 0.0}
    bs = ll = 0.0
    for r in scored:
        p = clamp(r.get("forecast_probability"))
        y = 1.0 if r.get("hit") else 0.0
        bs += (p - y) ** 2
        ll -= math.log(max(1e-6, p) if y else max(1e-6, 1.0 - p))
    return {"samples": len(scored), "brier_score": round(bs / len(scored), 6),
            "log_loss": round(ll / len(scored), 6),
            "coverage": round(len(scored) / len(rows), 4) if rows else 0.0}


def calibrate():
    rows = read()
    groups = {}
    for row in rows:
        try:
            key = (str(row.get("side") or "").upper(),
                   str(row.get("regime") or "UNKNOWN"),
                   int(row.get("horizon_hours") or 0))
            signed = float(row.get("signed_return") or 0)
        except (TypeError, ValueError):
            continue
        groups.setdefault(key, []).append(signed)
    cells = {}
    for (side, regime, horizon), values in groups.items():
        wins = sum(value > 0 for value in values)
        count = len(values)
        rate = wins / count
        probability = (wins + 1) / (count + 2)
        confidence = min(1.0, count / MIN)
        shrunk = 0.5 + (probability - 0.5) * confidence
        cells[f"{side}|{regime}|{horizon}h"] = {
            "side": side, "regime": regime, "horizon_hours": horizon,
            "samples": count, "wins": wins, "raw_rate": round(rate, 4),
            "calibrated_probability": round(shrunk, 4),
            "confidence": round(confidence, 4), "trusted": count >= MIN
        }
    return cells


def reliability(rows):
    bins = {}
    for row in rows:
        if row.get("forecast_probability") is None:
            continue
        probability = clamp(row.get("forecast_probability"))
        bucket = min(9, int(probability * 10))
        key = str(bucket)
        item = bins.setdefault(key, {"count": 0, "probability_sum": 0.0, "outcome_sum": 0})
        item["count"] += 1
        item["probability_sum"] += probability
        item["outcome_sum"] += 1 if row.get("hit") else 0
    return {key: {"samples": value["count"],
                  "mean_predicted": round(value["probability_sum"] / value["count"], 4),
                  "observed_rate": round(value["outcome_sum"] / value["count"], 4)}
            for key, value in bins.items()}


def main():
    rows = read()
    cells = calibrate()
    payload = {
        "schema": "NIC-FORECAST-CALIBRATION-3.0",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "minimum_events": MIN, "cells": cells, "global_metrics": metrics(rows),
        "reliability_bins": reliability(rows),
        "resolved_event_samples": len(rows),
        "policy": "Calibration joins terminal outcome events to immutable snapshots by forecast_id; unresolved outcomes are excluded. Legacy resolved snapshots remain readable. Brier score and log loss measure probabilistic quality; small samples are shrunk toward 50% and are never trusted."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps({"cells": len(main()["cells"])}))
