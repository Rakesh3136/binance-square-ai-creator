from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path

path=Path("src/nic22_3_publication_alignment_gate.py")
spec=importlib.util.spec_from_file_location("nic22_3_alignment",path)
gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)

def test_trade_setup_requires_matching_confirmation():
    now=datetime.now(timezone.utc)
    out=gate.evaluate(["technical_setup"],["KAIAUSDT"],{},now)
    assert out["allowed"] is False
    assert out["status"]=="BLOCKED_MISSING_OR_MISMATCHED_CONFIRMATION"

def test_same_symbol_fresh_confirmation_passes():
    now=datetime.now(timezone.utc)
    confirmation={"status":"CONFIRMED","generated_at":(now-timedelta(minutes=3)).isoformat(),
      "selected_opportunity":{"symbol":"KAIA","confirmation_status":"CONFIRMED_EARLY_SETUP"}}
    out=gate.evaluate(["technical_setup"],["KAIAUSDT"],confirmation,now)
    assert out["allowed"] is True
    assert out["status"]=="PASS_MATCHED_CONFIRMATION"

def test_different_symbol_confirmation_blocks():
    now=datetime.now(timezone.utc)
    confirmation={"status":"CONFIRMED","generated_at":now.isoformat(),
      "selected_opportunity":{"symbol":"ETH","confirmation_status":"CONFIRMED_EARLY_SETUP"}}
    out=gate.evaluate(["technical_setup"],["KAIA"],confirmation,now)
    assert out["allowed"] is False

def test_stale_confirmation_blocks():
    now=datetime.now(timezone.utc)
    confirmation={"status":"CONFIRMED","generated_at":(now-timedelta(hours=2)).isoformat(),
      "selected_opportunity":{"symbol":"KAIA","confirmation_status":"CONFIRMED_EARLY_SETUP"}}
    out=gate.evaluate(["technical_setup"],["KAIA"],confirmation,now)
    assert out["allowed"] is False

def test_non_trade_editorial_lane_is_not_blocked():
    out=gate.evaluate(["world_macro"],["KAIA"],{})
    assert out["allowed"] is True
    assert out["status"]=="PASS_NON_TRADE_LANE"

if __name__=="__main__":
    test_trade_setup_requires_matching_confirmation()
    test_same_symbol_fresh_confirmation_passes()
    test_different_symbol_confirmation_blocks()
    test_stale_confirmation_blocks()
    test_non_trade_editorial_lane_is_not_blocked()
    print("NIC 22.3 publication alignment tests passed")
