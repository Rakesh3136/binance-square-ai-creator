import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("calibrator",ROOT/"src/nic_forecast_calibrator.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_small_samples_are_shrunk():
    old=(m.LEDGER,m.EVENTS,m.OUT)
    m.LEDGER=ROOT/"tests"/"tmp_forecast_ledger.jsonl"
    m.EVENTS=ROOT/"tests"/"tmp_forecast_events.jsonl"
    m.OUT=ROOT/"tests"/"tmp_forecast_calibration.json"
    try:
        m.LEDGER.write_text(json.dumps({"forecast_id":"f1","resolved":True,"horizon_hours":6,"side":"BULLISH","regime":"RANGE","signed_return":10,"hit":True})+"\n")
        m.EVENTS.write_text("")
        cells=m.calibrate()
        c=cells["BULLISH|RANGE|6h"]
        assert c["calibrated_probability"] < 0.8
        assert c["trusted"] is False
    finally:
        for path in (m.LEDGER,m.EVENTS,m.OUT): path.unlink(missing_ok=True)
        m.LEDGER,m.EVENTS,m.OUT=old

def test_probability_metrics_are_computed():
    metrics=m.metrics([{"forecast_probability":0.8,"hit":True},{"forecast_probability":0.2,"hit":False}])
    assert metrics["samples"]==2
    assert metrics["brier_score"]==0.04
    assert metrics["log_loss"]>0

def test_terminal_events_join_to_immutable_snapshots():
    old=(m.LEDGER,m.EVENTS,m.OUT)
    m.LEDGER=ROOT/"tests"/"tmp_forecast_ledger.jsonl"
    m.EVENTS=ROOT/"tests"/"tmp_forecast_events.jsonl"
    m.OUT=ROOT/"tests"/"tmp_forecast_calibration.json"
    snapshot={"forecast_id":"f-1","symbol":"ABC","side":"BULLISH","regime":"RANGE","horizon_hours":6,"entry_price":100,"forecast_probability":0.8,"resolved":False}
    event={"event_type":"FORECAST_RESOLVED","event_id":"f-1|resolved","forecast_id":"f-1","symbol":"ABC","side":"BULLISH","horizon_hours":6,"signed_return":2.0,"hit":True}
    try:
        m.LEDGER.write_text(json.dumps(snapshot)+"\n")
        m.EVENTS.write_text(json.dumps(event)+"\n")
        rows=m.read()
        assert len(rows)==1 and rows[0]["resolved"] is True
        assert rows[0]["outcome_source"]=="terminal_event"
        assert m.metrics(rows)["samples"]==1
        assert m.calibrate(rows)["BULLISH|RANGE|6h"]["wins"]==1
    finally:
        for path in (m.LEDGER,m.EVENTS,m.OUT): path.unlink(missing_ok=True)
        m.LEDGER,m.EVENTS,m.OUT=old

def test_unresolved_forecasts_are_not_scored():
    rows=[{"forecast_id":"open","horizon_hours":6,"side":"BULLISH","regime":"RANGE","forecast_probability":0.9,"resolved":False}]
    assert m.metrics(rows)["samples"]==0
    assert m.calibrate(rows)=={}

def test_conflicting_terminal_events_fail_closed():
    old=(m.LEDGER,m.EVENTS,m.OUT)
    m.LEDGER=ROOT/"tests"/"tmp_forecast_ledger.jsonl"
    m.EVENTS=ROOT/"tests"/"tmp_forecast_events.jsonl"
    m.OUT=ROOT/"tests"/"tmp_forecast_calibration.json"
    snapshot={"forecast_id":"f-2","symbol":"ABC","side":"BULLISH","regime":"RANGE","horizon_hours":6,"forecast_probability":0.7,"resolved":False}
    e1={"event_type":"FORECAST_RESOLVED","event_id":"f-2|resolved","forecast_id":"f-2","symbol":"ABC","side":"BULLISH","horizon_hours":6,"signed_return":1.0,"hit":True}
    e2={**e1,"event_id":"f-2|conflict","signed_return":-1.0,"hit":False}
    try:
        m.LEDGER.write_text(json.dumps(snapshot)+"\n")
        m.EVENTS.write_text(json.dumps(e1)+"\n"+json.dumps(e2)+"\n")
        try: m.read()
        except ValueError as exc: assert "conflicting terminal outcomes" in str(exc)
        else: raise AssertionError("conflicting terminal outcomes must fail closed")
    finally:
        for path in (m.LEDGER,m.EVENTS,m.OUT): path.unlink(missing_ok=True)
        m.LEDGER,m.EVENTS,m.OUT=old

if __name__=="__main__":
    test_small_samples_are_shrunk()
    test_probability_metrics_are_computed()
    test_terminal_events_join_to_immutable_snapshots()
    test_unresolved_forecasts_are_not_scored()
    test_conflicting_terminal_events_fail_closed()
    print("NIC forecast calibration tests passed")
