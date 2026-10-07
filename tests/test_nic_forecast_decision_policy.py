import importlib.util
from pathlib import Path
p=Path("src/nic_forecast_decision_policy.py")
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_wait_untrusted():
    r=m.evaluate({"calibrated_probability":.75,"probability_trusted":False,"evidence_score":8,"regime_stability":.9,"edge_decay_penalty":0.1,"side":"BULLISH"},"EARLY")
    assert r["decision"]=="WAIT"

def test_long_candidate():
    r=m.evaluate({"calibrated_probability":.74,"probability_trusted":True,"evidence_score":4,"regime_stability":.8,"edge_decay_penalty":.1,"side":"BULLISH"},"EARLY")
    assert r["decision"]=="LONG_CANDIDATE"

def test_timing_blocks():
    r=m.evaluate({"calibrated_probability":.74,"probability_trusted":True,"evidence_score":4,"regime_stability":.8,"edge_decay_penalty":.1,"side":"BULLISH"},"LATE")
    assert r["decision"]=="WAIT" and "timing_not_actionable" in r["reasons"]

if __name__=="__main__":
    test_wait_untrusted();test_long_candidate();test_timing_blocks();print("Decision policy tests: PASS")
