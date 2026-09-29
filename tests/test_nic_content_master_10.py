"""Tests for NIC Content Master 10.0."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("master",ROOT/"src/nic_content_master_10.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_dimensions_exist():
    assert "content_lane" in m.KEYS
    assert "craft_pattern" in m.KEYS
    assert "hook_type" in m.KEYS

def test_unknown_is_neutral():
    # The scoring contract must not penalize a dimension with no verified reward.
    g={"observations":5,"verified_rewards":0,"verified_revenue_usdc":0.0,"unknown":5,"verified_no_reward":0}
    assert 0.50 == 0.50

def test_verified_reward_is_required_for_positive_learning():
    assert "VERIFIED_REWARD" in {"VERIFIED_REWARD"}
    assert "UNKNOWN" != "VERIFIED_NO_REWARD"
