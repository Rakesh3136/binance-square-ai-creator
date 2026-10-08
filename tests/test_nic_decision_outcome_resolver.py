import importlib.util
from pathlib import Path
p=Path("src/nic_decision_outcome_resolver.py")
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_resolve():
    rows=[{"forecast_id":"X|1","resolved":True,"symbol":"X","side":"BULLISH","hit":True}]
    r=m.resolve(rows)
    assert len(r)==1 and r[0]["decision"]=="LONG_CANDIDATE" and r[0]["outcome"]=="WIN"

def test_wait():
    rows=[{"forecast_id":"X|2","resolved":True,"symbol":"X","side":"BEARISH","hit":False,"decision":"WAIT"}]
    r=m.resolve(rows)
    assert r[0]["outcome"]=="ABSTAINED"

if __name__=="__main__":
    test_resolve();test_wait();print("Decision outcome resolver tests: PASS")
