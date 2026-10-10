import importlib.util
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("calibrator", ROOT / "src/nic_forecast_calibrator.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_small_samples_are_shrunk():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text('{"forecast_id":"A","resolved":true,"horizon_hours":6,"side":"BULLISH","regime":"RANGE","signed_return":10}\n')
        events.write_text("")
        cell = m.calibrate()["BULLISH|RANGE|6h"]
        assert cell["calibrated_probability"] < 0.8
        assert cell["trusted"] is False
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events


def test_probability_metrics_are_computed():
    metrics = m.metrics([{"forecast_probability":0.8,"hit":True},{"forecast_probability":0.2,"hit":False}])
    assert metrics["samples"] == 2
    assert metrics["brier_score"] == 0.04
    assert metrics["log_loss"] > 0


def test_new_terminal_events_join_immutable_snapshots():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    snapshot = {"forecast_id":"A","timestamp":"2026-10-01T00:00:00+00:00","horizon_hours":6,
                "side":"BULLISH","regime":"RANGE","forecast_probability":0.8,"resolved":False}
    event = {"event_type":"FORECAST_RESOLVED","event_id":"A|resolved","forecast_id":"A",
             "signed_return":1.25,"hit":True}
    unresolved = {"forecast_id":"B","horizon_hours":6,"side":"BULLISH","regime":"RANGE",
                  "forecast_probability":0.9,"resolved":False}
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text("\n".join(json.dumps(x) for x in [snapshot, unresolved]) + "\n")
        events.write_text(json.dumps(event) + "\n")
        rows = m.read()
        assert len(rows) == 1 and rows[0]["forecast_id"] == "A"
        assert rows[0]["hit"] is True and rows[0]["signed_return"] == 1.25
        assert snapshot["resolved"] is False
        assert m.metrics(rows)["samples"] == 1
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events


def test_missing_or_unresolved_outcomes_are_not_scored():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text('{"forecast_id":"B","horizon_hours":24,"forecast_probability":0.99,"resolved":false}\n')
        events.write_text("")
        assert m.read() == []
        assert m.metrics(m.read())["samples"] == 0
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events


if __name__ == "__main__":
    test_small_samples_are_shrunk()
    test_probability_metrics_are_computed()
    test_new_terminal_events_join_immutable_snapshots()
    test_missing_or_unresolved_outcomes_are_not_scored()
    print("NIC forecast event-ledger calibration tests: PASS")
