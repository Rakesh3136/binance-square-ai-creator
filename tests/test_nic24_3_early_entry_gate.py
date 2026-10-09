from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("nic24_3_early_entry_gate",ROOT/"src/nic24_3_early_entry_gate.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

def test_extended_move_blocks():
    result=MODULE.evaluate("technical_setup",40.635,2.0,True)
    assert result["publish"] is False
    assert "asset_already_extended_for_new_entry" in result["failures"]

def test_small_fresh_move_passes():
    result=MODULE.evaluate("technical_setup",2.4,2.0,True)
    assert result["publish"] is True

def test_missing_market_evidence_blocks_trade():
    result=MODULE.evaluate("technical_setup",None,None,False)
    assert result["publish"] is False
    assert "missing_asset_market_move" in result["failures"]
    assert "missing_or_stale_market_snapshot" in result["failures"]

def test_editorial_lane_not_blocked_by_trade_timing_gate():
    result=MODULE.evaluate("research_insight",40.0,2.0,True)
    assert result["publish"] is True
    assert result["reason"] == "non_trade_editorial_lane"

if __name__=="__main__":
    test_extended_move_blocks()
    test_small_fresh_move_passes()
    test_missing_market_evidence_blocks_trade()
    test_editorial_lane_not_blocked_by_trade_timing_gate()
    print("NIC 24.3 early-entry gate tests passed")
