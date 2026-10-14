import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("profitability", ROOT / "src/nic_forecast_profitability.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_costs_can_turn_gross_win_into_net_loss():
    result = m.trade_metrics([{"signed_return_pct": 0.2}], 0.3)
    assert result["gross_mean_return_pct"] == 0.2
    assert result["net_mean_return_pct"] == -0.1
    assert result["net_winning_trades"] == 0


def test_profitability_requires_sufficient_chronological_heldout_evidence():
    rows = [{"forecast_id": str(i), "timestamp": f"2026-01-{(i % 28) + 1:02d}T00:00:00Z",
             "symbol": "BTC", "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6,
             "signed_return_pct": 1.0 if i % 3 else -0.2} for i in range(60)]
    report = m.evaluate(rows)
    assert report["status"] == "NOT_PROVEN"
    assert report["groups"]["BULLISH|6h"]["status"] == "NOT_PROVEN"
    assert report["publication_or_trade_authorization"] is False


def test_heldout_positive_edge_can_be_reported_but_never_authorizes_trading():
    rows = []
    for i in range(400):
        # Early segment mixed; later 120-row held-out segment positive after assumed costs.
        ret = ((-0.4 if i % 5 == 0 else 0.8) if i >= 280 else (0.5 if i % 2 else -0.4))
        rows.append({"forecast_id": str(i), "timestamp": f"{i:04d}", "side": "BULLISH", "decision": "LONG_CANDIDATE",
                     "horizon_hours": 6, "signed_return_pct": ret})
    rows.reverse()  # Input order must not leak future outcomes into the training segment.
    report = m.evaluate(rows)
    group = report["groups"]["BULLISH|6h"]
    assert group["status"] == "EXPLORATORY_SUBGROUP_CANDIDATE_NOT_PROOF"
    assert report["status"] == "NOT_PROVEN"
    assert report["portfolio_simulation_status"] == "INSUFFICIENT_ELIGIBLE_TRADES"
    assert report["publication_or_trade_authorization"] is False




def test_wait_and_legacy_rows_never_count_as_trades():
    rows = [
        {"forecast_id": "wait", "timestamp": "0001", "symbol": "BTC", "side": "BULLISH",
         "decision": "WAIT", "horizon_hours": 6, "signed_return_pct": 5.0},
        {"forecast_id": "legacy", "timestamp": "0002", "symbol": "ETH", "side": "BULLISH",
         "horizon_hours": 6, "signed_return_pct": 5.0},
        {"forecast_id": "wrong-side", "timestamp": "0003", "symbol": "SOL", "side": "BEARISH",
         "decision": "LONG_CANDIDATE", "horizon_hours": 6, "signed_return_pct": 5.0},
    ]
    report = m.evaluate(rows)
    assert report["status"] == "NOT_PROVEN"
    assert report["resolved_forecast_count"] == 3
    assert report["sample_count"] == 0
    assert report["excluded_non_actionable_count"] == 2
    assert report["excluded_legacy_missing_decision_count"] == 1
    assert report["groups"] == {}


def test_source_validator_counts_only_actionable_decisions():
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "truth.jsonl"
        events = Path(directory) / "outcomes.jsonl"
        snapshots = [
            {"forecast_id": "long", "timestamp": "2026-10-01T10:00:00Z", "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6,
             "source_provenance": {"provider": "Binance Spot Market Data API",
                 "endpoint": "https://data-api.binance.vision/api/v3/klines", "instrument": "BTCUSDT",
                 "interval": "1h", "closed_candle_open_time": "2026-10-01T09:00:00Z",
                 "closed_candle_as_of": "2026-10-01T10:00:00Z", "retrieved_at": "2026-10-01T10:00:01Z",
                 "strategy_spec_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}},
            {"forecast_id": "wait", "timestamp": "0002", "side": "BULLISH", "decision": "WAIT", "horizon_hours": 6},
            {"forecast_id": "legacy", "timestamp": "0003", "side": "BEARISH", "horizon_hours": 6},
        ]
        outcomes = [
            {"forecast_id": row["forecast_id"], "event_type": "FORECAST_RESOLVED",
             "signed_return": 0.5, "hit": True}
            for row in snapshots
        ]
        ledger.write_text("".join(__import__("json").dumps(row) + "\\n" for row in snapshots), encoding="utf-8")
        events.write_text("".join(__import__("json").dumps(row) + "\\n" for row in outcomes), encoding="utf-8")
        report = m.evaluate(m.load_resolved(snapshots, outcomes))
        report["source_evidence"] = {
            "snapshot_ledger_sha256": m.file_sha256(ledger),
            "outcome_ledger_sha256": m.file_sha256(events),
            "snapshot_count": len(snapshots),
            "terminal_outcome_count": len(outcomes),
            "resolved_forecast_count": len(snapshots),
        }
        m.validate_report_sources(report, snapshots, outcomes, ledger_path=ledger, events_path=events)
        assert report["resolved_forecast_count"] == 3
        assert report["sample_count"] == 1


def test_bad_cost_configuration_rejected():
    try:
        m.evaluate([], fee_per_side_pct=-0.1)
    except ValueError:
        return
    raise AssertionError("negative transaction costs must be rejected")


def test_jsonl_evidence_is_fail_closed():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ledger.jsonl"
        path.write_text('{broken}\n', encoding="utf-8")
        try:
            m.read_jsonl(path)
        except AssertionError as exc:
            assert "Malformed JSONL" in str(exc)
        else:
            raise AssertionError("malformed ledger must fail closed")


def test_profitability_report_is_bound_to_exact_source_ledgers():
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "truth.jsonl"
        events = Path(directory) / "outcomes.jsonl"
        ledger.write_text("", encoding="utf-8")
        events.write_text("", encoding="utf-8")
        report = m.evaluate([])
        report["source_evidence"] = {
            "snapshot_ledger_sha256": m.file_sha256(ledger),
            "outcome_ledger_sha256": m.file_sha256(events),
            "snapshot_count": 0,
            "terminal_outcome_count": 0,
            "resolved_forecast_count": 0,
        }
        m.validate_report_sources(report, [], [], ledger_path=ledger, events_path=events)
        report["status"] = "PROVISIONAL_POSITIVE_HELD_OUT"
        try:
            m.validate_report_sources(report, [], [], ledger_path=ledger, events_path=events)
        except AssertionError as exc:
            assert "Empty forecast ledger" in str(exc)
        else:
            raise AssertionError("empty source ledgers must never support a positive profitability claim")


def test_stale_source_hash_is_rejected():
    with tempfile.TemporaryDirectory() as directory:
        ledger = Path(directory) / "truth.jsonl"
        events = Path(directory) / "outcomes.jsonl"
        ledger.write_text("", encoding="utf-8")
        events.write_text("", encoding="utf-8")
        report = m.evaluate([])
        report["source_evidence"] = {
            "snapshot_ledger_sha256": "stale",
            "outcome_ledger_sha256": m.file_sha256(events),
            "snapshot_count": 0,
            "terminal_outcome_count": 0,
            "resolved_forecast_count": 0,
        }
        try:
            m.validate_report_sources(report, [], [], ledger_path=ledger, events_path=events)
        except AssertionError as exc:
            assert "snapshot_ledger_sha256" in str(exc)
        else:
            raise AssertionError("stale profitability reports must be rejected")


if __name__ == "__main__":
    test_costs_can_turn_gross_win_into_net_loss()
    test_profitability_requires_sufficient_chronological_heldout_evidence()
    test_heldout_positive_edge_can_be_reported_but_never_authorizes_trading()
    test_wait_and_legacy_rows_never_count_as_trades()
    test_bad_cost_configuration_rejected()
    test_jsonl_evidence_is_fail_closed()
    test_profitability_report_is_bound_to_exact_source_ledgers()
    test_stale_source_hash_is_rejected()
    print("NIC net profitability evaluation tests: PASS")


def test_legacy_resolved_snapshot_without_terminal_event_is_ignored():
    snapshot = {"forecast_id": "legacy", "resolved": True, "signed_return": 99,
                "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6}
    assert m.load_resolved([snapshot], []) == []


def test_loaded_resolved_rows_without_complete_provenance_are_excluded_from_metrics():
    snapshot = {"forecast_id": "f1", "timestamp": "2026-10-01T10:00:00Z",
                "symbol": "BTC", "side": "BULLISH", "decision": "LONG_CANDIDATE",
                "horizon_hours": 6, "source_provenance": {"url": "https://example.com"}}
    event = {"event_type": "FORECAST_RESOLVED", "forecast_id": "f1", "signed_return": 2.0,
             "resolved_at": "2026-10-01T16:00:00Z"}
    rows = m.load_resolved([snapshot], [event])
    report = m.evaluate(rows)
    assert report["resolved_forecast_count"] == 1
    assert report["sample_count"] == 0
    assert report["excluded_missing_source_provenance_count"] == 1
    assert report["status"] == "NOT_PROVEN"


def test_shadow_portfolio_blocks_same_symbol_overlap_and_reports_equity_metrics():
    rows = [
        {"forecast_id": "btc-1", "timestamp": "2026-10-01T00:00:00Z", "symbol": "BTC",
         "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6,
         "signed_return_pct": 1.0, "source_provenance_complete": True},
        {"forecast_id": "btc-overlap", "timestamp": "2026-10-01T03:00:00Z", "symbol": "BTC",
         "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6,
         "signed_return_pct": 9.0, "source_provenance_complete": True},
        {"forecast_id": "eth-1", "timestamp": "2026-10-01T01:00:00Z", "symbol": "ETH",
         "side": "BEARISH", "decision": "SHORT_CANDIDATE", "horizon_hours": 6,
         "signed_return_pct": -0.5, "source_provenance_complete": True},
        {"forecast_id": "legacy", "timestamp": "2026-10-01T00:00:00Z", "symbol": "SOL",
         "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 6,
         "signed_return_pct": 99.0, "source_provenance_complete": False},
    ]
    report = m.simulate_non_overlapping_portfolio(rows, round_trip_cost_pct=0.3,
                                                  initial_equity=10000, max_positions=2)
    assert report["status"] == "SIMULATED_SHADOW_ONLY"
    assert report["accepted_trade_count"] == 2
    assert report["skipped_same_symbol_overlap_count"] == 1
    assert report["skipped_missing_provenance_count"] == 1
    assert report["final_equity"] == 9995.0
    assert report["net_pnl"] == -5.0
    assert report["profit_factor"] == 0.875
    assert report["limitations"]


def test_shadow_portfolio_does_not_mix_horizons_or_claim_profitability():
    rows = [{"forecast_id": "long-24h", "timestamp": "2026-10-01T00:00:00Z", "symbol": "BTC",
             "side": "BULLISH", "decision": "LONG_CANDIDATE", "horizon_hours": 24,
             "signed_return_pct": 4.0, "source_provenance_complete": True}]
    report = m.evaluate(rows)
    assert report["status"] == "NOT_PROVEN"
    assert report["shadow_portfolio_simulation"]["accepted_trade_count"] == 0
    assert report["shadow_portfolio_simulation"]["skipped_other_horizon_count"] == 1
    assert report["publication_or_trade_authorization"] is False


def test_production_evaluator_uses_isolated_prospective_ledgers():
    assert m.LEDGER.name == "nic_forecast_prospective_cohort.jsonl"
    assert m.EVENTS.name == "nic_forecast_prospective_outcome_events.jsonl"


def test_production_evaluator_uses_isolated_prospective_ledgers():
    assert m.LEDGER.name == "nic_forecast_prospective_cohort.jsonl"
    assert m.EVENTS.name == "nic_forecast_prospective_outcome_events.jsonl"
