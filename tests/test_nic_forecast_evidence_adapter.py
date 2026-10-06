import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=ROOT/"src/nic_forecast_evidence_adapter.py"
ns={}
exec(spec.read_text(),ns)
def test_unknown_side_is_neutral():
    e=ns["evidence"]("BTC","")
    assert e["side"]==""
    assert e["evidence_score"]==0
    assert e["advisory_only"] is True
