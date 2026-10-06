import importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("rt",ROOT/"src/nic_regime_transition.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_transition_and_stability():
    rows=[{"symbol":"AAA","timestamp":str(i),"regime":"RANGE"} for i in range(8)]
    rows += [{"symbol":"AAA","timestamp":str(i+8),"regime":"TREND_UP"} for i in range(4)]
    e=m.evaluate("AAA",history=rows,matrix={})
    assert e["transition_state"]=="TRANSITION"
    assert e["regime_stability"]==1.0
    assert e["edge_decay_penalty"]>=0.35
def test_stable_state():
    rows=[{"symbol":"AAA","timestamp":str(i),"regime":"RANGE"} for i in range(8)]
    e=m.evaluate("AAA",history=rows,matrix={})
    assert e["transition_state"]=="STABLE"
    assert e["regime_stability"]==1.0
