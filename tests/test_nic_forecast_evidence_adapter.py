import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("forecast_adapter",ROOT/"src/nic_forecast_evidence_adapter.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
def test_unknown_side_is_neutral():
    e=mod.evidence("BTC","")
    assert e["side"]==""
    assert e["evidence_score"]==0
    assert e["advisory_only"] is True
