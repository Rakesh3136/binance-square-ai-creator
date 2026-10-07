import importlib.util
from pathlib import Path
p=Path("src/nic_forecast_champion.py")
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def rows(probs, hits):
    return [{"resolved":True,"forecast_probability":p,"hit":h,"timestamp":f"2026-01-{i+1:02d}T00:00:00+00:00"} for i,(p,h) in enumerate(zip(probs,hits))]

def test_no_champion_small_sample():
    r=m.evaluate(rows([.8,.2],[True,False]))
    assert r["state"]=="NO_CHAMPION" and r["champion"] is None

def test_champion_contract():
    r=m.evaluate(rows([.8]*20+[.55]*20,[True]*20+[False]*20))
    assert r["champion"] in {"BASELINE_RAW","CONSERVATIVE","CALIBRATED_SHRINK","CONFIDENT"}
    assert len(r["challengers"])==4
    assert all(x["state"] in {"CHAMPION","CHALLENGER"} for x in r["challengers"])

if __name__=="__main__":
    test_no_champion_small_sample(); test_champion_contract(); print("Champion/challenger tests: PASS")
