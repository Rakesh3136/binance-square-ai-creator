"""NIC Portfolio Reality Engine: cost-aware, non-overlapping shadow simulations.

Each side/horizon is evaluated as a separate, pre-defined strategy policy. This is
not exchange-account PnL, live execution, trade authorization, or a promise of profit.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS = ROOT / "data/intelligence/nic_forecast_outcome_events.jsonl"
OUT = ROOT / "data/intelligence/nic_portfolio_reality.json"
INITIAL_EQUITY = 10_000.0
ALLOCATION_FRACTION = 0.10
MAX_CONCURRENT_POSITIONS = 5
FEE_PER_SIDE_PCT = 0.10
SLIPPAGE_PER_SIDE_PCT = 0.05
MIN_TOTAL = 300
MIN_TEST = 100
LOWER_BOUND_Z = 2.64


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


def parse_time(value: str) -> datetime:
    if not value:
        raise AssertionError("Forecast timestamp is missing")
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AssertionError("Forecast timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def join_resolved(snapshots: list[dict], events: list[dict]) -> list[dict]:
    terminal = {}
    for event in events:
        if event.get("event_type") != "FORECAST_RESOLVED":
            continue
        fid = str(event.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Terminal event missing forecast_id")
        if fid in terminal:
            raise AssertionError(f"Duplicate terminal outcome for {fid}")
        terminal[fid] = event

    seen = set()
    rows = []
    for snap in snapshots:
        fid = str(snap.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Snapshot missing forecast_id")
        if fid in seen:
            raise AssertionError(f"Duplicate immutable snapshot {fid}")
        seen.add(fid)
        event = terminal.get(fid)
        if event is None and snap.get("resolved"):
            event = snap
        if event is None:
            continue
        side = str(snap.get("side") or "").upper()
        decision = str(snap.get("decision") or "").upper()
        expected = {"BULLISH": "LONG_CANDIDATE", "BEARISH": "SHORT_CANDIDATE"}.get(side)
        if expected is None or decision != expected:
            continue
        try:
            horizon = int(snap.get("horizon_hours") or 0)
            ret = float(event.get("signed_return", snap.get("signed_return")))
            symbol = str(snap.get("symbol") or event.get("symbol") or "").upper()
            entry = parse_time(str(snap.get("timestamp") or ""))
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"Invalid resolved forecast {fid}") from exc
        if horizon not in (6, 12, 24) or not symbol or not math.isfinite(ret):
            raise AssertionError(f"Invalid strategy fields for {fid}")
        rows.append({
            "forecast_id": fid,
            "timestamp": entry.isoformat(),
            "symbol": symbol,
            "side": side,
            "horizon_hours": horizon,
            "signed_return_pct": ret,
            "exit_time": (entry + timedelta(hours=horizon)).isoformat(),
        })
    orphan = set(terminal) - seen
    if orphan:
        raise AssertionError(f"Terminal outcomes without immutable snapshots: {len(orphan)}")
    return sorted(rows, key=lambda row: (row["timestamp"], row["symbol"], row["forecast_id"]))


def portfolio_simulate(rows: list[dict], *, initial_equity=INITIAL_EQUITY,
                       allocation_fraction=ALLOCATION_FRACTION,
                       max_positions=MAX_CONCURRENT_POSITIONS,
                       round_trip_cost_pct=2 * (FEE_PER_SIDE_PCT + SLIPPAGE_PER_SIDE_PCT)) -> dict:
    if initial_equity <= 0 or not 0 < allocation_fraction <= 1:
        raise ValueError("Initial equity and allocation fraction must be positive and bounded")
    if max_positions < 1 or not math.isfinite(round_trip_cost_pct) or round_trip_cost_pct < 0:
        raise ValueError("Position cap must be positive and round-trip cost non-negative")
    ordered = sorted(rows, key=lambda r: (parse_time(r["timestamp"]), r["symbol"], r["forecast_id"]))
    equity = float(initial_equity)
    peak = equity
    max_drawdown = 0.0
    open_positions = []
    realized = []
    skipped_overlap = 0
    skipped_capacity = 0
    cost_pct = float(round_trip_cost_pct)

    def close_due(cutoff: datetime):
        nonlocal equity, peak, max_drawdown, open_positions
        due = sorted((p for p in open_positions if parse_time(p["exit_time"]) <= cutoff),
                     key=lambda p: (p["exit_time"], p["forecast_id"]))
        due_ids = {p["forecast_id"] for p in due}
        for position in due:
            pnl = position["notional"] * position["net_return_pct"] / 100.0
            equity += pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
            realized.append({
                "forecast_id": position["forecast_id"],
                "symbol": position["symbol"],
                "entry_time": position["timestamp"],
                "exit_time": position["exit_time"],
                "notional": round(position["notional"], 4),
                "gross_return_pct": round(position["gross_return_pct"], 6),
                "net_return_pct": round(position["net_return_pct"], 6),
                "pnl": round(pnl, 4),
                "equity_after_close": round(equity, 4),
            })
        open_positions = [p for p in open_positions if p["forecast_id"] not in due_ids]

    for row in ordered:
        entry = parse_time(row["timestamp"])
        close_due(entry)
        if any(p["symbol"] == row["symbol"] for p in open_positions):
            skipped_overlap += 1
            continue
        if len(open_positions) >= max_positions:
            skipped_capacity += 1
            continue
        gross = float(row["signed_return_pct"])
        if not math.isfinite(gross):
            raise AssertionError("Non-finite outcome return")
        notional = equity * allocation_fraction
        open_positions.append({
            **row,
            "notional": notional,
            "gross_return_pct": gross,
            "net_return_pct": gross - cost_pct,
        })

    close_due(datetime.max.replace(tzinfo=timezone.utc))
    pnl_values = [float(x["pnl"]) for x in realized]
    returns = [float(x["net_return_pct"]) for x in realized]
    count = len(realized)
    avg = sum(returns) / count if count else None
    std = (math.sqrt(sum((x - avg) ** 2 for x in returns) / (count - 1))
           if count > 1 and avg is not None else None)
    lower = avg - LOWER_BOUND_Z * std / math.sqrt(count) if count > 1 and std is not None else None
    wins = sum(x > 0 for x in pnl_values)
    positive = sum(x for x in pnl_values if x > 0)
    negative = abs(sum(x for x in pnl_values if x < 0))
    pf = positive / negative if negative else (None if positive == 0 else "INF")
    return {
        "trades_closed": count,
        "starting_equity": round(initial_equity, 4),
        "ending_equity": round(equity, 4),
        "net_pnl": round(equity - initial_equity, 4),
        "net_return_pct": round((equity / initial_equity - 1) * 100, 5),
        "net_win_rate": round(wins / count, 5) if count else None,
        "profit_factor": round(pf, 5) if isinstance(pf, (int, float)) else pf,
        "mean_net_trade_return_pct": round(avg, 6) if avg is not None else None,
        "mean_return_lower_bound_pct": round(lower, 6) if lower is not None else None,
        "max_drawdown_pct_of_initial_equity": round(max_drawdown / initial_equity * 100, 5),
        "max_concurrent_positions": max_positions,
        "allocation_fraction_per_position": allocation_fraction,
        "skipped_overlapping_same_symbol": skipped_overlap,
        "skipped_position_capacity": skipped_capacity,
        "round_trip_cost_pct": round(cost_pct, 5),
        "trade_log": realized,
    }


def evaluate(snapshots: list[dict], events: list[dict], *,
             fee_per_side_pct=FEE_PER_SIDE_PCT,
             slippage_per_side_pct=SLIPPAGE_PER_SIDE_PCT) -> dict:
    if not all(math.isfinite(float(x)) and float(x) >= 0 for x in (fee_per_side_pct, slippage_per_side_pct)):
        raise ValueError("Fee and slippage assumptions must be finite and non-negative")
    rows = join_resolved(snapshots, events)
    groups = {}
    for row in rows:
        groups.setdefault((row["side"], row["horizon_hours"]), []).append(row)
    results = {}
    round_trip_cost = 2 * (float(fee_per_side_pct) + float(slippage_per_side_pct))
    for (side, horizon), items in sorted(groups.items()):
        items = sorted(items, key=lambda r: (r["timestamp"], r["symbol"], r["forecast_id"]))
        split = max(1, int(len(items) * 0.7))
        train = items[:split]
        raw_test = items[split:]
        # Purge one holding horizon after the chronological boundary to prevent
        # a position opened in the training segment overlapping the test segment.
        boundary = parse_time(raw_test[0]["timestamp"]) + timedelta(hours=horizon) if raw_test else None
        test = [r for r in raw_test if boundary is not None and parse_time(r["timestamp"]) >= boundary]
        train_result = portfolio_simulate(train, round_trip_cost_pct=round_trip_cost)
        test_result = portfolio_simulate(test, round_trip_cost_pct=round_trip_cost)
        eligible = (
            len(items) >= MIN_TOTAL and test_result["trades_closed"] >= MIN_TEST
            and test_result["net_pnl"] > 0
            and isinstance(test_result["profit_factor"], (int, float))
            and test_result["profit_factor"] > 1
            and test_result["mean_return_lower_bound_pct"] is not None
            and test_result["mean_return_lower_bound_pct"] > 0
        )
        results[f"{side}|{horizon}h"] = {
            "side": side,
            "horizon_hours": horizon,
            "total_candidates": len(items),
            "chronological_train": train_result,
            "purged_held_out_test": test_result,
            "status": "EXPLORATORY_SHADOW_CANDIDATE_NOT_PROOF" if eligible else "NOT_PROVEN",
            "reason": ("Positive purged held-out portfolio simulation; still requires untouched final holdout, robust cost stress, multiple-testing correction, and measured execution."
                       if eligible else "Insufficient evidence or held-out portfolio failed the predeclared net-profit, profit-factor, or lower-bound criteria."),
        }
    return {
        "schema": "NIC-PORTFOLIO-REALITY-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "NOT_PROVEN",
        "mode": "SHADOW_ONLY_NO_LIVE_ORDERS",
        "source_evidence": {
            "snapshot_ledger_sha256": hashlib.sha256(json.dumps(snapshots, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "outcome_ledger_sha256": hashlib.sha256(json.dumps(events, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "snapshot_count": len(snapshots),
            "terminal_outcome_count": sum(x.get("event_type") == "FORECAST_RESOLVED" for x in events),
            "resolved_actionable_forecasts": len(rows),
        },
        "cost_assumptions": {
            "fee_per_side_pct": float(fee_per_side_pct),
            "slippage_per_side_pct": float(slippage_per_side_pct),
            "round_trip_cost_pct": round(round_trip_cost, 5),
            "notional_fraction_per_position": ALLOCATION_FRACTION,
            "maximum_concurrent_positions_per_policy": MAX_CONCURRENT_POSITIONS,
        },
        "strategy_groups": results,
        "limitations": [
            "Every side/horizon is simulated as a separate policy; results must not be added together as one portfolio.",
            "Returns are price-return proxies from historical candles, not exchange-account fills or realized PnL.",
            "Funding, borrow, spread variation, market impact, partial fills, taxes, and liquidation are not modeled.",
            "This report never authorizes trades or publication and cannot establish future profitability.",
            "Top-level status stays NOT_PROVEN even if a subgroup passes exploratory shadow criteria.",
        ],
        "trade_or_publication_authorization": False,
    }


def main():
    snapshots = read_jsonl(LEDGER)
    events = read_jsonl(EVENTS)
    report = evaluate(snapshots, events,
                      fee_per_side_pct=float(__import__("os").getenv("NIC_FEE_PER_SIDE_PCT", str(FEE_PER_SIDE_PCT))),
                      slippage_per_side_pct=float(__import__("os").getenv("NIC_SLIPPAGE_PER_SIDE_PCT", str(SLIPPAGE_PER_SIDE_PCT))))
    report["source_file_evidence"] = {
        "snapshot_ledger_sha256": sha256(LEDGER),
        "outcome_ledger_sha256": sha256(EVENTS),
        "snapshot_bytes": LEDGER.stat().st_size if LEDGER.exists() else 0,
        "outcome_bytes": EVENTS.stat().st_size if EVENTS.exists() else 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "snapshots": report["source_evidence"]["snapshot_count"],
        "terminal_outcomes": report["source_evidence"]["terminal_outcome_count"],
        "resolved_actionable": report["source_evidence"]["resolved_actionable_forecasts"],
        "strategy_groups": len(report["strategy_groups"]),
        "trade_or_publication_authorization": False,
    }))
    return report


if __name__ == "__main__":
    main()
