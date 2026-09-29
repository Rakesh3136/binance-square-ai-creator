"""Tests for NIC Content Craft Intelligence 9.0."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("craft",ROOT/"src/nic_content_craft_intelligence_9.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_lane_contracts():
    assert m.ARCHETYPES["data_investigation"][0]=="data_surprise"
    assert m.ARCHETYPES["breaking_news"][0]=="event_reaction"
    assert m.ARCHETYPES["outcome_accountability"][0]=="call_vs_result"

def test_forbidden_content_is_internal_or_pressure():
    assert "attention score" in m.FORBIDDEN_INTERNAL
    assert "buy now" in m.TRADE_PRESSURE

def test_generic_hooks_are_detectable():
    s="For $QNT, that matters because volume changed."
    assert any(x in s.lower() for x in m.GENERIC_HOOKS)

def test_asset_swap_normalization():
    import re
    text="For $QNT, volume expanded while price rose."
    normalized=re.sub(r"\$?[A-Z0-9]{2,15}","$ASSET",text.upper())
    assert normalized=="FOR $ASSET, VOLUME EXPANDED WHILE PRICE ROSE."
