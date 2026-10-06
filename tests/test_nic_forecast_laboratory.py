import importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location("lab",Path("src/nic_forecast_laboratory.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_regime():
 assert m.regime({"rsi":75,"momentum":8,"trend":1,"volume_ratio":1})=="TREND_UP_EXTENDED"
 assert m.regime({"rsi":25,"momentum":-8,"trend":-1,"volume_ratio":1})=="TREND_DOWN_EXTENDED"
 assert m.regime({"rsi":55,"momentum":2,"trend":1,"volume_ratio":1})=="TREND_UP"
def test_wait():
 assert m.summarize([1,-1])["hit_rate"]==.5
def test_signal_audit_contract():
 x=m.walkforward([{"c":100,"h":101,"l":99,"v":100}]*150,"BULLISH","volume_expansion")
 assert set(("feature","base","conditional","lift","eligible","predictive"))<=set(x)
if __name__=="__main__": test_regime();test_wait();test_signal_audit_contract();print("Forecast Laboratory learning tests passed")
