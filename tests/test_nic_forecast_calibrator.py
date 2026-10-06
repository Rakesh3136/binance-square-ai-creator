import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("calibrator",ROOT/"src/nic_forecast_calibrator.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_small_samples_are_shrunk():
    m.LEDGER=ROOT/"tests"/"tmp_forecast_ledger.jsonl"
    m.LEDGER.write_text('{"resolved":true,"horizon_hours":6,"side":"BULLISH","regime":"RANGE","signed_return":10}\n')
    cells=m.calibrate()
    c=cells["BULLISH|RANGE|6h"]
    assert c["calibrated_probability"] < 0.8
    assert c["trusted"] is False
    m.LEDGER.unlink(missing_ok=True)
    m.OUT.unlink(missing_ok=True)


def test_probability_metrics_are_computed():
    rows=[{"forecast_probability":0.8,"hit":True},{"forecast_probability":0.2,"hit":False}]
    m=__import__("nic_forecast_calibrator") if False else None
    metrics=globals()["m"].metrics(rows)
    assert metrics["samples"]==2
    assert metrics["brier_score"]==0.04
    assert metrics["log_loss"]>0
