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
