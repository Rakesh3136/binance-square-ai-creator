from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location("fg",Path(__file__).resolve().parents[1]/"src/nic_signal_family_governance.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert m.metric([{"hit":True},{"hit":False}])["hit_rate"]==0.5
print("NIC Signal Family Governance tests: PASS")
