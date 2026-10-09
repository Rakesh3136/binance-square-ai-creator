"""Regression tests for advisory Forecast Laboratory integration in NIC 22.2."""
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("nic22_2",Path("src/nic22_2_early_opportunity_engine.py"))
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def test_forecast_wait_never_removes_or_penalizes_candidate(monkeypatch):
    monkeypatch.setattr(mod, "num", mod.num)
    c={"symbol":"TEST","price_change_percent":2.0,"relative_strength_24h":1.0,
       "raw_score":60.0,"adjusted_score":60.0}
    monkeypatch.setitem(__import__("sys").modules,"nic_forecast_evidence_adapter",
        type("Adapter",(),{"evidence":staticmethod(lambda symbol,side: {
            "symbol":symbol,"side":"BULLISH","probability_trusted":False,
            "evidence_score":0,"decision_policy":{"decision":"WAIT"},
            "advisory_only":True,"publish_gate_unchanged":True})})())
    out=mod.attach_forecast_evidence(c)
    assert out["adjusted_score"]==60.0
    assert out["forecast_evidence"]["eligibility_gate_unchanged"] is True
    assert out["forecast_evidence"]["ranking_bonus"]==0

def test_trusted_matching_forecast_gets_bounded_bonus(monkeypatch):
    import sys
    sys.modules["nic_forecast_evidence_adapter"]=type("Adapter",(),{"evidence":staticmethod(lambda symbol,side: {
        "symbol":symbol,"side":"BULLISH","probability_trusted":True,"evidence_score":8,
        "decision_policy":{"decision":"LONG_CANDIDATE"},
        "advisory_only":True,"publish_gate_unchanged":True})})()
    out=mod.attach_forecast_evidence({"symbol":"TEST","price_change_percent":2,
        "relative_strength_24h":1,"raw_score":60,"adjusted_score":60})
    assert out["adjusted_score"]==64
    assert out["forecast_evidence"]["trusted_directional_alignment"] is True
    assert out["forecast_evidence"]["ranking_bonus"]<=5

def test_direction_conflict_or_missing_direction_has_no_bonus(monkeypatch):
    import sys
    sys.modules["nic_forecast_evidence_adapter"]=type("Adapter",(),{"evidence":staticmethod(lambda symbol,side: {
        "probability_trusted":True,"evidence_score":10,
        "decision_policy":{"decision":"LONG_CANDIDATE"},
        "advisory_only":True,"publish_gate_unchanged":True})})()
    out=mod.attach_forecast_evidence({"symbol":"TEST","price_change_percent":2,
        "relative_strength_24h":-1,"raw_score":60,"adjusted_score":60})
    assert out["adjusted_score"]==60
    assert out["forecast_evidence"]["ranking_bonus"]==0
