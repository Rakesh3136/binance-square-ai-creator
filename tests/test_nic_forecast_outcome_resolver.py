from src.nic_forecast_outcome_resolver import rebuild
import json
def test_unresolved_not_trusted(tmp_path,monkeypatch):
 import src.nic_forecast_outcome_resolver as r
 monkeypatch.setattr(r,"MATRIX",tmp_path/"m.json")
 rows=[{"resolved":True,"side":"BULLISH","feature":"trend_aligned","regime":"TREND_UP","hit":True,"signed_return":1} for _ in range(29)]
 rebuild(rows)
 assert list(json.loads((tmp_path/"m.json").read_text())["matrix"].values())[0]["trusted"] is False
