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


def has_complete_source_provenance(snapshot: dict) -> bool:
    """Require source details sufficient to reproduce a forecast's market observation."""
    source = snapshot.get("source_provenance")
    if not isinstance(source, dict):
        return False
    required = ("provider", "endpoint", "instrument", "interval", "closed_candle_open_time",
                "closed_candle_as_of", "retrieved_at", "strategy_spec_sha256")
    if any(not isinstance(source.get(key), str) or not source[key].strip() for key in required):
        return False
    if not source["endpoint"].startswith("https://") or not source["instrument"].strip():
        return False
    for key in ("closed_candle_open_time", "closed_candle_as_of", "retrieved_at"):
        try:
            datetime.fromisoformat(source[key].replace("Z", "+00:00"))
        except ValueError:
            return False
    digest = source["strategy_spec_sha256"]
    return len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest.lower())


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
        # Only explicit terminal outcome events can resolve a forecast. A legacy
        # snapshot's mutable resolved=true flag is not an outcome event and is ignored.
        event = by_id.get(fid)
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
            "decision": str(snap.get("decision") or "").upper(),
            "forecast_probability": finite_float(snap.get("forecast_probability")),
            "signed_return_pct": signed,
            "source_provenance_complete": has_complete_source_provenance(snap),
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




def _parse_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def simulate_non_overlapping_portfolio(
    rows: list[dict],
    round_trip_cost_pct: float,
    initial_equity: float = 10_000.0,
    max_positions: int = 5,
    fixed_horizon_hours: int = 6,
) -> dict:
    """Deterministic shadow portfolio; fixed horizon, no same-symbol overlap, no live orders.

    Uses only explicit actionable resolved forecasts with complete provenance when the
    loader has assessed it. Position notional is fixed at initial_equity/max_positions,
    avoiding look-ahead sizing or compounding. This is a directional return proxy,
    not exchange-account PnL; no intratrade mark-to-market is available.
    """
    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("initial_equity must be finite and positive")
    if max_positions < 1 or fixed_horizon_hours < 1:
        raise ValueError("max_positions and fixed_horizon_hours must be positive")
    cost = finite_float(round_trip_cost_pct)
    if cost is None or cost < 0:
        raise ValueError("round_trip_cost_pct must be finite and non-negative")

    candidates = []
    skipped_invalid_timestamp = 0
    skipped_missing_provenance = 0
    skipped_non_actionable = 0
    skipped_other_horizon = 0
    for row in rows:
        if row.get("source_provenance_complete") is False:
            skipped_missing_provenance += 1
            continue
        try:
            horizon = int(row.get("horizon_hours") or 0)
        except (TypeError, ValueError):
            horizon = 0
        if horizon != fixed_horizon_hours:
            skipped_other_horizon += 1
            continue
        side = str(row.get("side") or "").upper()
        decision = str(row.get("decision") or "").upper()
        expected = {"BULLISH": "LONG_CANDIDATE", "BEARISH": "SHORT_CANDIDATE"}.get(side)
        if expected is None or decision != expected:
            skipped_non_actionable += 1
            continue
        entry = _parse_timestamp(str(row.get("timestamp") or ""))
        gross = finite_float(row.get("signed_return_pct"))
        symbol = str(row.get("symbol") or "").upper().strip()
        if entry is None or gross is None or not symbol:
            skipped_invalid_timestamp += 1
            continue
        candidates.append({**row, "_entry": entry, "_exit": entry + __import__("datetime").timedelta(hours=fixed_horizon_hours),
                           "_net_return_pct": gross - cost, "_symbol": symbol})

    candidates.sort(key=lambda row: (row["_entry"], row["_symbol"], str(row.get("forecast_id") or "")))
    active = []
    equity = float(initial_equity)
    peak = equity
    max_drawdown_pct = 0.0
    accepted = []
    skipped_overlap = 0
    skipped_capacity = 0
    fixed_notional = initial_equity / max_positions

    def close_until(cutoff=None, close_all=False):
        nonlocal equity, peak, max_drawdown_pct, active
        closing = [position for position in active if close_all or position["_exit"] <= cutoff]
        closing.sort(key=lambda position: (position["_exit"], position["_symbol"], str(position.get("forecast_id") or "")))
        for position in closing:
            equity += fixed_notional * position["_net_return_pct"] / 100.0
            peak = max(peak, equity)
            if peak > 0:
                max_drawdown_pct = max(max_drawdown_pct, (peak - equity) / peak * 100.0)
            accepted.append({
                "forecast_id": str(position.get("forecast_id") or ""),
                "symbol": position["_symbol"],
                "entry_at": position["_entry"].isoformat(),
                "exit_at": position["_exit"].isoformat(),
                "horizon_hours": fixed_horizon_hours,
                "gross_return_pct": round(position["_net_return_pct"] + cost, 5),
                "net_return_pct": round(position["_net_return_pct"], 5),
                "notional": round(fixed_notional, 2),
                "net_pnl": round(fixed_notional * position["_net_return_pct"] / 100.0, 5),
            })
        active = [position for position in active if position not in closing]

    for candidate in candidates:
        close_until(candidate["_entry"])
        if any(position["_symbol"] == candidate["_symbol"] for position in active):
            skipped_overlap += 1
            continue
        if len(active) >= max_positions:
            skipped_capacity += 1
            continue
        active.append(candidate)
    close_until(close_all=True)

    pnl_values = [trade["net_pnl"] for trade in accepted]
    wins = sum(value > 0 for value in pnl_values)
    gross_profit = sum(value for value in pnl_values if value > 0)
    gross_loss = abs(sum(value for value in pnl_values if value < 0))
    return {
        "status": "SIMULATED_SHADOW_ONLY" if accepted else "INSUFFICIENT_ELIGIBLE_TRADES",
        "method": "chronological fixed-6h horizon; max five concurrent positions; same-symbol overlap blocked",
        "initial_equity": round(initial_equity, 2),
        "final_equity": round(equity, 5),
        "net_pnl": round(equity - initial_equity, 5),
        "total_return_pct": round((equity / initial_equity - 1.0) * 100.0, 5),
        "accepted_trade_count": len(accepted),
        "net_win_rate": round(wins / len(accepted), 5) if accepted else None,
        "profit_factor": round(gross_profit / gross_loss, 5) if gross_loss else (None if not gross_profit else "INF"),
        "max_closed_equity_drawdown_pct": round(max_drawdown_pct, 5),
        "fixed_notional_per_position": round(fixed_notional, 2),
        "max_positions": max_positions,
        "fixed_horizon_hours": fixed_horizon_hours,
        "skipped_same_symbol_overlap_count": skipped_overlap,
        "skipped_position_capacity_count": skipped_capacity,
        "skipped_missing_provenance_count": skipped_missing_provenance,
        "skipped_non_actionable_count": skipped_non_actionable,
        "skipped_other_horizon_count": skipped_other_horizon,
        "skipped_invalid_timestamp_or_return_count": skipped_invalid_timestamp,
        "closed_trades": accepted,
        "limitations": [
            "Uses directional signed-return proxies, not verified exchange fills or account PnL.",
            "Fixed position notional and close-to-close outcome labels omit intratrade path, stop/target order, funding, borrow, liquidation and real execution.",
            "A simulated result is not out-of-sample proof, does not authorize trading, and must not be presented as a guaranteed edge.",
        ],
    }


def evaluate(rows: list[dict], fee_per_side_pct=0.1, slippage_per_side_pct=0.05) -> dict:
    fee = finite_float(fee_per_side_pct)
    slippage = finite_float(slippage_per_side_pct)
    if fee is None or slippage is None or fee < 0 or slippage < 0:
        raise ValueError("Fees and slippage must be finite non-negative percentages")
    cost = 2 * (fee + slippage)

    # Only the action explicitly selected by the forecast policy is eligible for
    # the trade-return proxy. WAIT and legacy rows without an action are not trades.
    actionable = []
    excluded_missing_decision = 0
    excluded_non_actionable = 0
    excluded_missing_provenance = 0
    for row in rows:
        # Production rows are tagged by load_resolved; direct evaluator fixtures
        # without this field remain useful for unit-testing the metric arithmetic.
        if row.get("source_provenance_complete") is False:
            excluded_missing_provenance += 1
            continue
        side = str(row.get("side") or "").upper()
        decision = str(row.get("decision") or "").upper()
        expected = {"BULLISH": "LONG_CANDIDATE", "BEARISH": "SHORT_CANDIDATE"}.get(side)
        if not decision:
            excluded_missing_decision += 1
        elif expected is None or decision != expected:
            excluded_non_actionable += 1
        else:
            actionable.append(row)

    groups = {}
    for row in actionable:
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
            "status": "EXPLORATORY_SUBGROUP_CANDIDATE_NOT_PROOF" if proven else "NOT_PROVEN",
            "reason": ("Positive chronological subgroup only; multiple testing, overlapping signals, execution and portfolio-level profitability remain unproven."
                       if proven else "Requires >=100 actionable forecasts, >=30 later held-out outcomes, positive held-out net expectancy and profit factor >1 after assumed costs."),
        }
    all_metrics = trade_metrics(actionable, cost)
    portfolio = simulate_non_overlapping_portfolio(rows, cost)
    candidates = [key for key, value in report_groups.items()
                  if value["status"] == "EXPLORATORY_SUBGROUP_CANDIDATE_NOT_PROOF"]
    return {
        "schema": "NIC-FORECAST-PROFITABILITY-1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # A positive subgroup is a research lead, not proof that the complete
        # deployed strategy is profitable. This evaluator does not yet simulate
        # non-overlapping positions, portfolio sizing, stops/targets or real fills.
        "status": "NOT_PROVEN",
        "exploratory_subgroup_candidates": candidates,
        "mode": "SHADOW_EVALUATION_ONLY",
        "resolved_forecast_count": len(rows),
        "sample_count": len(actionable),
        "excluded_non_actionable_count": excluded_non_actionable,
        "excluded_legacy_missing_decision_count": excluded_missing_decision,
        "excluded_missing_source_provenance_count": excluded_missing_provenance,
        "portfolio_simulation_status": portfolio["status"],
        "shadow_portfolio_simulation": portfolio,
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
            "Only explicit LONG_CANDIDATE/SHORT_CANDIDATE forecasts enter the trade-return proxy; WAIT and legacy rows without decisions are excluded.",
            "Positive subgroup results are exploratory only; the top-level strategy remains NOT_PROVEN until a pre-registered, non-overlapping portfolio simulation passes held-out testing.",
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
    resolved_rows = load_resolved(snapshots, events)
    actionable_count = sum(
        1 for row in resolved_rows
        if row.get("source_provenance_complete") is not False and (
            (str(row.get("side") or "").upper() == "BULLISH"
             and str(row.get("decision") or "").upper() == "LONG_CANDIDATE")
            or
            (str(row.get("side") or "").upper() == "BEARISH"
             and str(row.get("decision") or "").upper() == "SHORT_CANDIDATE")
        )
    )
    if report.get("sample_count") != actionable_count:
        raise AssertionError(
            "Profitability sample count does not match actionable resolved forecasts "
            f"(reported={report.get('sample_count')}, expected={actionable_count})"
        )
    if not snapshots and report.get("status") != "NOT_PROVEN":
        raise AssertionError("Empty forecast ledger cannot support a profitability claim")
    if report.get("status") == "PROVISIONAL_POSITIVE_HELD_OUT":
        groups = report.get("groups") or {}
        if not any(
            group.get("status") == "PROVISIONAL_POSITIVE_HELD_OUT"
            and (group.get("held_out_test") or {}).get("net_mean_return_lower_bound_pct", 0) > 0
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
