import importlib.util
from pathlib import Path
p=Path("src/nic_decision_outcome.py");s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_win_loss():
    assert m.score("LONG_CANDIDATE","BULLISH",True)["utility"]==1.0
    assert m.score("SHORT_CANDIDATE","BEARISH",False)["utility"]==-1.0

def test_wait():
    assert m.score("WAIT","BULLISH",None)["outcome"]=="UNRESOLVED"

def test_summary():
    r=m.summarize([{"outcome":"WIN","utility":1},{"outcome":"LOSS","utility":-1},{"outcome":"ABSTAINED","utility":.25}])
    assert r["samples"]==3 and r["abstention_rate"]>0

if __name__=="__main__":
    test_win_loss();test_wait();test_summary();print("Decision outcome tests: PASS")
