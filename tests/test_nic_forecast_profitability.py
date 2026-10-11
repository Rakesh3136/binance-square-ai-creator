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
    assert report["portfolio_simulation_status"] == "NOT_IMPLEMENTED"
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
