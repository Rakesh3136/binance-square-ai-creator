"""Regression tests for NIC Editorial Quality 3.1 conversion repair."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("gate",ROOT/"src/nic_editorial_quality_gate.py")
gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)

def test_missing_asset_and_action_are_repaired_within_budget():
    text=("HBAR is holding the stated level while volume remains mixed. "
          "The useful signal is whether the next response confirms the setup. "
          "What evidence should change the thesis first?")
    out, repairs=gate.conversion_repair(text,"HBAR")
    assert "$HBAR" in out
    assert gate.ACTION_WORDS.search(out)
    assert len(out)<=gate.MAX_CHARS
    assert repairs

def test_trade_pressure_is_not_repaired_away():
    assert gate.TRADE_PRESSURE.search("buy now")


def test_write_json_emits_parseable_json_with_real_newline(tmp_path):
    import json
    path=tmp_path/"report.json"
    payload={"status":"PASS","draft":{"post":"real draft"}}
    gate.write_json(path,payload)
    raw=path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert not raw.endswith("\\n")
    assert json.loads(raw)==payload
