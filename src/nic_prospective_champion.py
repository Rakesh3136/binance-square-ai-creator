"""NIC prospective champion: pre-registered, forward-only shadow cohort evaluation.

This module deliberately never declares a strategy proven and never authorizes
publication or orders. It scores only forecasts carrying the frozen prospective
strategy version/spec hash and only outcomes recorded after their horizon matured.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import nic_forecast_laboratory as lab  # noqa: E402
import nic_portfolio_reality_engine as portfolio  # noqa: E402

LEDGER = ROOT / "data/intelligence/nic_forecast_truth_ledger.jsonl"
EVENTS = ROOT / "data/intelligence/nic_forecast_outcome_events.jsonl"
OUT = ROOT / "data/intelligence/nic_prospective_champion.json"
MIN_TOTAL = 300
MIN_TEST = 100
FEE_PER_SIDE_PCT = 0.10
SLIPPAGE_PER_SIDE_PCT = 0.05
STRESS_ROUND_TRIP_COST_PCT = 0.50
LOWER_BOUND_Z = 2.64


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Malformed JSONL at {path.name}:{line_no}") from exc
        if not isinstance(row, dict):
            raise AssertionError(f"Non-object JSONL row at {path.name}:{line_no}")
        rows.append(row)
    return rows


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def parse_time(value: str) -> datetime:
    if not value:
        raise AssertionError("Prospective forecast timestamp is missing")
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AssertionError("Prospective timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_frozen_snapshot(snap: dict) -> bool:
    if snap.get("strategy_version") != lab.STRATEGY_VERSION:
        return False
    if snap.get("validation_status") != "PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN":
        return False
    spec = snap.get("strategy_spec")
    if not isinstance(spec, dict):
        return False
    digest = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != snap.get("strategy_spec_sha256"):
        raise AssertionError("Frozen strategy spec hash does not match its payload")
    if digest != lab.STRATEGY_SPEC_SHA256:
        # A changed specification must be evaluated as a different version/cohort.
        return False
    timestamp = parse_time(str(snap.get("timestamp") or ""))
    frozen_at = parse_time(str(snap.get("strategy_frozen_at") or ""))
    if timestamp < frozen_at:
        raise AssertionError("Forecast predates the strategy freeze timestamp")
    horizon = int(snap.get("horizon_hours") or 0)
    if horizon not in (6, 12, 24):
        return False
    return True


def prospective_rows(snapshots: list[dict], events: list[dict]) -> tuple[list[dict], dict]:
    terminal = {}
    for event in events:
        if event.get("event_type") != "FORECAST_RESOLVED":
            continue
        fid = str(event.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Terminal outcome is missing forecast_id")
        if fid in terminal:
            raise AssertionError(f"Duplicate terminal outcome for {fid}")
        terminal[fid] = event

    seen = set()
    selected = []
    cohort_snapshots = 0
    unresolved = 0
    excluded_non_actionable = 0
    for snap in snapshots:
        fid = str(snap.get("forecast_id") or "")
        if not fid:
            raise AssertionError("Snapshot is missing forecast_id")
        if fid in seen:
            raise AssertionError(f"Duplicate immutable forecast ID {fid}")
        seen.add(fid)
        if snap.get("strategy_version") != lab.STRATEGY_VERSION:
            continue
        if not validate_frozen_snapshot(snap):
            continue
        cohort_snapshots += 1
        event = terminal.get(fid)
        if event is None:
            unresolved += 1
            continue
        side = str(snap.get("side") or "").upper()
        decision = str(snap.get("decision") or "").upper()
        expected = {"BULLISH": "LONG_CANDIDATE", "BEARISH": "SHORT_CANDIDATE"}.get(side)
        if expected is None or decision != expected:
            excluded_non_actionable += 1
            continue
        ts = parse_time(str(snap.get("timestamp") or ""))
        frozen_at = parse_time(str(snap.get("strategy_frozen_at") or ""))
        horizon = int(snap.get("horizon_hours") or 0)
        resolved_at = parse_time(str(event.get("resolved_at") or ""))
        if ts < frozen_at:
            raise AssertionError(f"Forecast {fid} predates frozen strategy")
        if resolved_at < ts + timedelta(hours=horizon):
            raise AssertionError(f"Outcome for {fid} resolved before its horizon matured")
        try:
            ret = float(event.get("signed_return"))
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"Outcome for {fid} has invalid signed return") from exc
        if not math.isfinite(ret):
            raise AssertionError(f"Outcome for {fid} has non-finite signed return")
        symbol = str(snap.get("symbol") or "").upper()
        if not symbol:
            raise AssertionError(f"Forecast {fid} has no symbol")
        selected.append({
            "forecast_id": fid,
            "timestamp": ts.isoformat(),
            "exit_time": (ts + timedelta(hours=horizon)).isoformat(),
            "symbol": symbol,
            "side": side,
            "horizon_hours": horizon,
            "signed_return_pct": ret,
            "strategy_version": lab.STRATEGY_VERSION,
            "strategy_spec_sha256": snap["strategy_spec_sha256"],
            "regime": str(snap.get("regime") or "UNKNOWN"),
        })
    orphan_events = set(terminal) - seen
    if orphan_events:
        # Older events may legitimately correspond to historical snapshots. An event
        # without any snapshot at all is a ledger-integrity problem.
        raise AssertionError(f"Terminal outcomes without snapshots: {len(orphan_events)}")
    return sorted(selected, key=lambda row: (row["timestamp"], row["symbol"], row["forecast_id"])), {
        "cohort_snapshot_count": cohort_snapshots,
        "cohort_resolved_actionable_count": len(selected),
        "cohort_unresolved_count": unresolved,
        "cohort_excluded_non_actionable_count": excluded_non_actionable,
    }


def chronological_split(rows: list[dict], *, train_fraction: float = 0.70) -> tuple[list[dict], list[dict], str | None]:
    ordered = sorted(rows, key=lambda row: (row["timestamp"], row["symbol"], row["forecast_id"]))
    if len(ordered) < 2:
        return ordered, [], None
    split_index = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    boundary = parse_time(ordered[split_index]["timestamp"])
    # Purge any training position whose holding window touches the test period.
    train = [row for row in ordered[:split_index] if parse_time(row["exit_time"]) <= boundary]
    test = [row for row in ordered[split_index:] if parse_time(row["timestamp"]) >= boundary]
    return train, test, boundary.isoformat()


def evaluate(snapshots: list[dict], events: list[dict], *, min_total: int = MIN_TOTAL,
             min_test: int = MIN_TEST, fee_per_side_pct: float = FEE_PER_SIDE_PCT,
             slippage_per_side_pct: float = SLIPPAGE_PER_SIDE_PCT,
             stress_round_trip_cost_pct: float = STRESS_ROUND_TRIP_COST_PCT) -> dict:
    for value in (fee_per_side_pct, slippage_per_side_pct, stress_round_trip_cost_pct):
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError("All cost assumptions must be finite and non-negative")
    rows, counts = prospective_rows(snapshots, events)
    groups = {}
    for row in rows:
        key = (row["strategy_version"], row["strategy_spec_sha256"], row["side"], row["horizon_hours"])
        groups.setdefault(key, []).append(row)

    cost = 2 * (fee_per_side_pct + slippage_per_side_pct)
    reports = {}
    promising_groups = []
    review_groups = []
    for (version, spec_hash, side, horizon), items in sorted(groups.items()):
        train, test, boundary = chronological_split(items)
        train_metrics = portfolio.portfolio_simulate(train, round_trip_cost_pct=cost)
        test_metrics = portfolio.portfolio_simulate(test, round_trip_cost_pct=cost)
        stress_metrics = portfolio.portfolio_simulate(test, round_trip_cost_pct=stress_round_trip_cost_pct)
        enough = len(items) >= min_total and test_metrics["trades_closed"] >= min_test
        profitable = (
            test_metrics["net_pnl"] > 0
            and isinstance(test_metrics["profit_factor"], (int, float))
            and test_metrics["profit_factor"] > 1.0
            and test_metrics["mean_return_lower_bound_pct"] is not None
            and test_metrics["mean_return_lower_bound_pct"] > 0
        )
        stress_pass = (
            stress_metrics["net_pnl"] > 0
            and isinstance(stress_metrics["profit_factor"], (int, float))
            and stress_metrics["profit_factor"] > 1.0
            and stress_metrics["mean_return_lower_bound_pct"] is not None
            and stress_metrics["mean_return_lower_bound_pct"] > 0
        )
        if not enough:
            status = "COLLECTING_PROSPECTIVE_OUTCOMES"
        elif profitable and stress_pass:
            status = "CANDIDATE_FOR_HUMAN_REVIEW_NOT_PROOF"
            review_groups.append(f"{side}|{horizon}h")
        elif test_metrics["net_pnl"] > 0:
            status = "PROMISING_BUT_NOT_PROVEN"
            promising_groups.append(f"{side}|{horizon}h")
        else:
            status = "NOT_PROVEN"
        reports[f"{side}|{horizon}h"] = {
            "strategy_version": version,
            "strategy_spec_sha256": spec_hash,
            "side": side,
            "horizon_hours": horizon,
            "prospective_resolved_candidates": len(items),
            "chronological_train_candidates": len(train),
            "purged_held_out_test_candidates": len(test),
            "test_boundary_utc": boundary,
            "chronological_train": train_metrics,
            "purged_held_out_test": test_metrics,
            "execution_cost_stress_test": {
                "round_trip_cost_pct": stress_round_trip_cost_pct,
                "metrics": stress_metrics,
                "passed": bool(enough and stress_pass),
            },
            "status": status,
            "promotion_allowed": False,
        }
    status = "COLLECTING_PROSPECTIVE_OUTCOMES"
    if review_groups:
        status = "CANDIDATE_FOR_HUMAN_REVIEW_NOT_PROOF"
    elif promising_groups:
        status = "PROMISING_BUT_NOT_PROVEN"
    return {
        "schema": "NIC-PROSPECTIVE-CHAMPION-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "SHADOW_ONLY",
        "strategy_version": lab.STRATEGY_VERSION,
        "strategy_spec_sha256": lab.STRATEGY_SPEC_SHA256,
        "sample_counts": counts,
        "minimum_total_candidates": min_total,
        "minimum_held_out_candidates": min_test,
        "cost_assumptions": {
            "fee_per_side_pct": fee_per_side_pct,
            "slippage_per_side_pct": slippage_per_side_pct,
            "base_round_trip_cost_pct": round(cost, 5),
            "stress_round_trip_cost_pct": stress_round_trip_cost_pct,
            "lower_bound_z": LOWER_BOUND_Z,
        },
        "strategy_groups": reports,
        "promising_groups_not_proof": promising_groups,
        "human_review_candidates_not_proof": review_groups,
        "source_evidence": {
            "snapshot_ledger_sha256": file_sha256(LEDGER),
            "outcome_ledger_sha256": file_sha256(EVENTS),
            "snapshot_count": len(snapshots),
            "terminal_outcome_count": sum(x.get("event_type") == "FORECAST_RESOLVED" for x in events),
        },
        "trade_authorization": False,
        "publication_or_trade_authorization": False,
        "note": "Prospective cohort evidence only. Even a review candidate is not proof of future profitability and never authorizes a trade or publication.",
    }


def main() -> None:
    snapshots = read_jsonl(LEDGER)
    events = read_jsonl(EVENTS)
    report = evaluate(snapshots, events)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "sample_counts": report["sample_counts"],
        "strategy_groups": len(report["strategy_groups"]),
        "trade_authorization": False,
    }))


if __name__ == "__main__":
    main()
