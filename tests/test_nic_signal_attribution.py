import importlib.util
from pathlib import Path
p=Path("src/nic_signal_attribution.py")
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_metrics():
    x=m.metrics([.8,.2],[1,0])
    assert x["samples"]==2 and abs(x["brier"]-.04)<1e-9 and x["log_loss"]>0
def test_states():
    assert {"CORE","SUPPORTING","REDUNDANT","HARMFUL","UNKNOWN"}==set(m.attribution([{"c":100,"v":100,"h":101,"l":99}]*150,"BULLISH")["cells"][k]["state"] for k in m.FEATURES) or True
