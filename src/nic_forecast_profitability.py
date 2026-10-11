"""Cost-aware, shadow-only profitability evaluation for NIC's matured forecasts.

This evaluates directional return proxies after explicit round-trip fee/slippage
assumptions. It is not an exchange account PnL ledger and never authorizes trading.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS = ROOT / "data/intelligence/nic_forecast_outcome_events.jsonl"
OUT = ROOT / "data/intelligence/nic_forecast_profitability.json"
MIN_TOTAL = 300
MIN_TEST = 100
# One-sided 99% lower bound with a conservative six-cell multiple-testing adjustment.
EDGE_LOWER_BOUND_Z = 2.64


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Malformed JSONL evidence in {path.name}") from exc
        if not isinstance(row, dict):
            raise AssertionError(f"Non-object evidence row in {path.name}")
        rows.append(row)
    return rows


def finite_float(value, default=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def load_resolved(snapshots: list[dict], events: list[dict]) -> list[dict]:
    by_id = {}
    for event in events:
        if event.get("event_type") != "FORECAST_RESOLVED":
            continue
        fid = str(event.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Terminal outcome event is missing forecast_id")
        if fid in by_id:
            raise AssertionError(f"Duplicate terminal outcomes for {fid}")
        by_id[fid] = event
    seen = set()
    rows = []
    for snap in snapshots:
        fid = str(snap.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Forecast snapshot is missing forecast_id")
        if fid in seen:
            raise AssertionError(f"Duplicate forecast snapshot {fid}")
        seen.add(fid)
        event = by_id.get(fid)
        if event is None and snap.get("resolved"):
            event = snap
        if event is None:
            continue
        signed = finite_float(event.get("signed_return"))
        if signed is None:
            raise AssertionError(f"Resolved forecast {fid} has invalid signed_return")
        if "hit" in event and bool(event["hit"]) != (signed > 0):
            raise AssertionError(f"Resolved forecast {fid} has inconsistent hit label")
        try:
            horizon = int(snap.get("horizon_hours") or 0)
        except (TypeError, ValueError):
            continue
        if horizon not in (6, 12, 24):
            continue
        rows.append({
            "forecast_id": fid,
            "timestamp": str(snap.get("timestamp") or event.get("resolved_at") or ""),
            "symbol": str(snap.get("symbol") or event.get("symbol") or ""),
            "side": str(snap.get("side") or event.get("side") or "").upper(),
            "regime": str(snap.get("regime") or event.get("regime") or "UNKNOWN"),
            "horizon_hours": horizon,
            "signed_return_pct": signed,
        })
    orphan = set(by_id) - seen
    if orphan:
        raise AssertionError(f"Terminal outcomes without immutable snapshots: {len(orphan)}")
    return sorted(rows, key=lambda row: (row["timestamp"], row["forecast_id"]))


def trade_metrics(rows: list[dict], round_trip_cost_pct: float) -> dict:
    gross = [finite_float(row.get("signed_return_pct")) for row in rows]
    gross = [value for value in gross if value is not None]
    net = [value - round_trip_cost_pct for value in gross]
    wins = [value for value in net if value > 0]
    losses = [value for value in net if value < 0]
    equity = peak = max_drawdown = 0.0
    # Equal-weight, non-compounded percentage-point curve; transparent and conservative.
    for value in net:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    positive_sum = sum(wins)
    negative_sum = abs(sum(losses))
    count = len(net)
    expectancy = sum(net) / count if count else None
    sample_std = (math.sqrt(sum((value - expectancy) ** 2 for value in net) / (count - 1))
                  if count > 1 and expectancy is not None else None)
    lower_bound = (expectancy - EDGE_LOWER_BOUND_Z * sample_std / math.sqrt(count)
                   if count > 1 and sample_std is not None else None)
    return {
        "samples": count,
        "gross_mean_return_pct": round(sum(gross) / count, 5) if count else None,
        "net_mean_return_pct": round(expectancy, 5) if count else None,
        "net_mean_return_lower_bound_pct": round(lower_bound, 5) if lower_bound is not None else None,
        "confidence_bound": "one-sided 99% normal-approximation lower bound; z=2.64 for six-group screening",
        "net_total_return_pct_points": round(sum(net), 5) if count else None,
        "net_win_rate": round(len(wins) / count, 5) if count else None,
        "profit_factor": round(positive_sum / negative_sum, 5) if negative_sum else (None if not wins else "INF"),
        "max_drawdown_pct_points": round(max_drawdown, 5),
        "net_winning_trades": len(wins),
        "net_losing_trades": len(losses),
        "cost_drag_pct_points": round(round_trip_cost_pct * count, 5),
    }


def evaluate(rows: list[dict], fee_per_side_pct=0.1, slippage_per_side_pct=0.05) -> dict:
    fee = finite_float(fee_per_side_pct)
    slippage = finite_float(slippage_per_side_pct)
    if fee is None or slippage is None or fee < 0 or slippage < 0:
        raise ValueError("Fees and slippage must be finite non-negative percentages")
    cost = 2 * (fee + slippage)
    groups = {}
    for row in rows:
        key = (str(row.get("side") or "UNKNOWN").upper(), int(row.get("horizon_hours") or 0))
        groups.setdefault(key, []).append(row)
    report_groups = {}
    for (side, horizon), items in sorted(groups.items()):
        items = sorted(items, key=lambda row: (str(row.get("timestamp") or ""), str(row.get("forecast_id") or "")))
        split = max(1, int(len(items) * 0.7))
        train, test = items[:split], items[split:]
        total_metrics = trade_metrics(items, cost)
        test_metrics = trade_metrics(test, cost)
        proven = (
            len(items) >= MIN_TOTAL and len(test) >= MIN_TEST
            and test_metrics["net_mean_return_pct"] is not None
            and test_metrics["net_mean_return_pct"] > 0
            and test_metrics["profit_factor"] != "INF"
            and isinstance(test_metrics["profit_factor"], (int, float))
            and test_metrics["profit_factor"] > 1.0
        )
        report_groups[f"{side}|{horizon}h"] = {
            "side": side, "horizon_hours": horizon,
            "total": total_metrics, "chronological_train": trade_metrics(train, cost),
            "held_out_test": test_metrics,
            "status": "PROVISIONAL_POSITIVE_HELD_OUT" if proven else "NOT_PROVEN",
            "reason": None if proven else "Requires >=300 matured forecasts, >=100 later held-out outcomes, positive net expectancy, profit factor >1, and a positive one-sided 99% lower confidence bound after assumed costs.",
        }
    all_metrics = trade_metrics(rows, cost)
    return {
        "schema": "NIC-FORECAST-PROFITABILITY-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PROVISIONAL_POSITIVE_HELD_OUT" if any(x["status"] == "PROVISIONAL_POSITIVE_HELD_OUT" for x in report_groups.values()) else "NOT_PROVEN",
        "mode": "SHADOW_EVALUATION_ONLY",
        "sample_count": len(rows),
        "cost_assumptions": {
            "fee_per_side_pct": fee, "slippage_per_side_pct": slippage,
            "round_trip_cost_pct": round(cost, 5),
            "source": "Configurable assumptions; replace with actual account-specific fees and measured execution slippage before making PnL claims.",
        },
        "all_resolved_forecasts": all_metrics,
        "groups": report_groups,
        "limitations": [
            "Directional price-return proxy, not verified exchange-account PnL.",
            "Bearish returns assume short-direction exposure; borrow, funding, leverage, liquidation and venue constraints are excluded.",
            "No claim of predictive edge until chronological held-out outcomes pass the sample and net-return criteria.",
            "Overlapping forecasts can be statistically dependent; the report is not a guarantee of future profits.",
        ],
        "publication_or_trade_authorization": False,
    }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def validate_report_sources(report: dict, snapshots: list[dict], events: list[dict],
                            ledger_path: Path = LEDGER, events_path: Path = EVENTS) -> dict:
    """Fail closed if profitability metrics are not tied to the exact persisted source files."""
    evidence = report.get("source_evidence")
    if not isinstance(evidence, dict):
        raise AssertionError("Profitability report is missing source-evidence provenance")
    expected = {
        "snapshot_ledger_sha256": file_sha256(ledger_path),
        "outcome_ledger_sha256": file_sha256(events_path),
        "snapshot_count": len(snapshots),
        "terminal_outcome_count": sum(x.get("event_type") == "FORECAST_RESOLVED" for x in events),
        "resolved_forecast_count": len(load_resolved(snapshots, events)),
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise AssertionError(f"Profitability source evidence mismatch for {key}")
    if report.get("sample_count") != expected["resolved_forecast_count"]:
        raise AssertionError("Profitability sample count does not match current immutable source evidence")
    if not snapshots and report.get("status") != "NOT_PROVEN":
        raise AssertionError("Empty forecast ledger cannot support a profitability claim")
    if report.get("status") == "PROVISIONAL_POSITIVE_HELD_OUT":
        groups = report.get("groups") or {}
        if not any(
            group.get("status") == "PROVISIONAL_POSITIVE_HELD_OUT"
            and (group.get("held_out_test") or {}).get("net_mean_return_lower_bound_pct", 0) > 0
            and (group.get("held_out_test") or {}).get("profit_factor", 0) not in (None, "INF")
            and isinstance((group.get("held_out_test") or {}).get("profit_factor"), (int, float))
            and (group.get("held_out_test") or {}).get("profit_factor") > 1
            for group in groups.values()
        ):
            raise AssertionError("Positive profitability status lacks a qualifying held-out group")
    return expected


def main():
    snapshots = read_jsonl(LEDGER)
    events = read_jsonl(EVENTS)
    rows = load_resolved(snapshots, events)
    report = evaluate(
        rows,
        fee_per_side_pct=os.getenv("NIC_FEE_PER_SIDE_PCT", "0.1"),
        slippage_per_side_pct=os.getenv("NIC_SLIPPAGE_PER_SIDE_PCT", "0.05"),
    )
    report["source_evidence"] = {
        "snapshot_ledger_sha256": file_sha256(LEDGER),
        "outcome_ledger_sha256": file_sha256(EVENTS),
        "snapshot_count": len(snapshots),
        "terminal_outcome_count": sum(x.get("event_type") == "FORECAST_RESOLVED" for x in events),
        "resolved_forecast_count": len(rows),
    }
    report["proof_policy"] = {
        "minimum_total_per_side_horizon": MIN_TOTAL,
        "minimum_held_out_per_side_horizon": MIN_TEST,
        "required_held_out_net_expectancy": "positive",
        "required_profit_factor": "> 1 after assumed costs",
        "required_confidence_bound": "positive one-sided 99% normal-approximation lower bound; six-group screening adjustment",
        "status_ceiling": "PROVISIONAL_POSITIVE_HELD_OUT; never a guarantee or trade authorization",
    }
    validate_report_sources(report, snapshots, events)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "resolved_forecasts": len(rows),
        "groups": len(report["groups"]), "cost_round_trip_pct": report["cost_assumptions"]["round_trip_cost_pct"],
        "publication_or_trade_authorization": False,
    }))
    return report


if __name__ == "__main__":
    main()
