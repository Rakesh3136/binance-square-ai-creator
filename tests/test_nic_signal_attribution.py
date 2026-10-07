import importlib.util
from pathlib import Path
p=Path("src/nic_signal_attribution.py")
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_metrics():
    x=m.metrics([.8,.2],[1,0])
    assert x["samples"]==2 and abs(x["brier"]-.04)<1e-9 and x["log_loss"]>0

def test_states_contract():
    rows=[{"c":100+i*0.1,"v":100,"h":101,"l":99} for i in range(160)]
    result=m.attribution(rows,"BULLISH")
    assert set(result["cells"]) == set(m.FEATURES)
    assert all(v["state"] in {"CORE","SUPPORTING","REDUNDANT","HARMFUL","UNKNOWN"} for v in result["cells"].values())
    assert all(0.0 < v["trust_multiplier"] <= 1.0 for v in result["cells"].values())

if __name__=="__main__":
    test_metrics(); test_states_contract(); print("Signal attribution tests: PASS")
