import importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location("lab",Path("src/nic_forecast_laboratory.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_regime():
 assert m.regime({"rsi":75,"momentum":8,"trend":1,"volume_ratio":1})=="TREND_UP_EXTENDED"
 assert m.regime({"rsi":25,"momentum":-8,"trend":-1,"volume_ratio":1})=="TREND_DOWN_EXTENDED"
 assert m.regime({"rsi":55,"momentum":2,"trend":1,"volume_ratio":1})=="TREND_UP"
if __name__=="__main__":test_regime();print("Forecast Laboratory unit tests passed")
