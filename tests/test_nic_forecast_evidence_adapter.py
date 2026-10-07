import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("forecast_adapter",ROOT/"src/nic_forecast_evidence_adapter.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
def test_unknown_side_is_neutral():
    e=mod.evidence("BTC","")
    assert e["side"]==""
    assert e["evidence_score"]==0
    assert e["calibrated_probability"]==0.5
    assert e["probability_trusted"] is False
    assert e["advisory_only"] is True
def test_evidence_exposes_governance_controls():
    e=mod.evidence("BTC","LONG")
    assert "regime_stability" in e
    assert "edge_decay_penalty" in e
    assert "signal_family_trust_multiplier" in e
    assert "suspended_cells" in e
