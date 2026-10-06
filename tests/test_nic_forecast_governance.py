from pathlib import Path
import importlib.util, tempfile, json

spec=importlib.util.spec_from_file_location("gov",Path(__file__).resolve().parents[1]/"src/nic_forecast_governance.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

rows=[{"forecast_probability":0.8,"hit":True,"resolved_at":"1"},
      {"forecast_probability":0.2,"hit":False,"resolved_at":"2"}]
assert m._metrics(rows)["samples"]==2
assert m._metrics(rows)["brier_score"]==0.04

assert m._state(rows)=="RECOVERY"
print("NIC Forecast Governance tests: PASS")
