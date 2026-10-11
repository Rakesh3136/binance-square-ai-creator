import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("portfolio_reality", ROOT / "src/nic_portfolio_reality_engine.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def snapshot(fid, ts, symbol, side="BULLISH", horizon=6, decision=None):
    return {"forecast_id": fid, "timestamp": ts, "symbol": symbol, "side": side,
            "horizon_hours": horizon,
            "decision": decision or ("LONG_CANDIDATE" if side == "BULLISH" else "SHORT_CANDIDATE")}


def event(fid, ret):
    return {"event_type": "FORECAST_RESOLVED", "forecast_id": fid, "signed_return": ret}


def test_non_actionable_waits_are_excluded():
    snaps = [snapshot("a", "2026-01-01T00:00:00Z", "BTC", decision="WAIT")]
    report = m.evaluate(snaps, [event("a", 5.0)])
    assert report["status"] == "NOT_PROVEN"
    assert report["source_evidence"]["resolved_actionable_forecasts"] == 0
    assert report["strategy_groups"] == {}
    assert report["trade_or_publication_authorization"] is False


def test_simulation_deducts_cost_and_compounds_equity():
    rows = [{"forecast_id": "a", "timestamp": "2026-01-01T00:00:00Z",
             "exit_time": "2026-01-01T06:00:00Z", "symbol": "BTC", "signed_return_pct": 1.0}]
    result = m.portfolio_simulate(rows, initial_equity=1000, allocation_fraction=0.1,
                                  max_positions=2, round_trip_cost_pct=0.3)
    assert result["trades_closed"] == 1
    assert result["net_pnl"] == 0.7
    assert result["ending_equity"] == 1000.7


def test_same_symbol_overlap_and_capacity_are_skipped():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i, (sym, hour) in enumerate([("BTC", 0), ("BTC", 1), ("ETH", 1), ("SOL", 1)]):
        start = base + timedelta(hours=hour)
        rows.append({"forecast_id": str(i), "timestamp": start.isoformat(),
                     "exit_time": (start + timedelta(hours=6)).isoformat(),
                     "symbol": sym, "signed_return_pct": 1.0})
    result = m.portfolio_simulate(rows, max_positions=2)
    assert result["trades_closed"] == 2
    assert result["skipped_overlapping_same_symbol"] == 1
    assert result["skipped_position_capacity"] == 1


def test_orphan_terminal_event_fails_closed():
    try:
        m.join_resolved([], [event("orphan", 1.0)])
    except AssertionError as exc:
        assert "without immutable snapshots" in str(exc)
    else:
        raise AssertionError("orphan outcome must fail closed")


def test_duplicate_terminal_event_fails_closed():
    snap = snapshot("a", "2026-01-01T00:00:00Z", "BTC")
    try:
        m.join_resolved([snap], [event("a", 1.0), event("a", 1.0)])
    except AssertionError as exc:
        assert "Duplicate terminal outcome" in str(exc)
    else:
        raise AssertionError("duplicate terminal outcomes must fail closed")


def test_empty_ledgers_never_prove_profitability():
    report = m.evaluate([], [])
    assert report["status"] == "NOT_PROVEN"
    assert report["strategy_groups"] == {}
    assert report["source_evidence"]["snapshot_count"] == 0
    assert report["source_evidence"]["terminal_outcome_count"] == 0


if __name__ == "__main__":
    test_non_actionable_waits_are_excluded()
    test_simulation_deducts_cost_and_compounds_equity()
    test_same_symbol_overlap_and_capacity_are_skipped()
    test_orphan_terminal_event_fails_closed()
    test_duplicate_terminal_event_fails_closed()
    test_empty_ledgers_never_prove_profitability()
    print("NIC Portfolio Reality Engine tests: PASS")
