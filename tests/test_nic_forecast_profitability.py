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
             "symbol": "BTC", "side": "BULLISH", "horizon_hours": 6,
             "signed_return_pct": 1.0 if i % 3 else -0.2} for i in range(60)]
    report = m.evaluate(rows)
    assert report["status"] == "NOT_PROVEN"
    assert report["groups"]["BULLISH|6h"]["status"] == "NOT_PROVEN"
    assert report["publication_or_trade_authorization"] is False


def test_heldout_positive_edge_can_be_reported_but_never_authorizes_trading():
    rows = []
    for i in range(150):
        # Early segment mixed; later held-out segment positive after assumed 0.3% costs.
        ret = (0.8 if i >= 105 else (0.5 if i % 2 else -0.4))
        rows.append({"forecast_id": str(i), "timestamp": f"{i:04d}", "side": "BULLISH",
                     "horizon_hours": 6, "signed_return_pct": ret})
    report = m.evaluate(rows)
    group = report["groups"]["BULLISH|6h"]
    assert group["status"] == "PROVISIONAL_POSITIVE_HELD_OUT"
    assert report["status"] == "PROVISIONAL_POSITIVE_HELD_OUT"
    assert report["publication_or_trade_authorization"] is False


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


if __name__ == "__main__":
    test_costs_can_turn_gross_win_into_net_loss()
    test_profitability_requires_sufficient_chronological_heldout_evidence()
    test_heldout_positive_edge_can_be_reported_but_never_authorizes_trading()
    test_bad_cost_configuration_rejected()
    test_jsonl_evidence_is_fail_closed()
    print("NIC net profitability evaluation tests: PASS")
