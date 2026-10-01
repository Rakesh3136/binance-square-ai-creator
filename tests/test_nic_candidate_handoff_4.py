import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "src")
import nic_candidate_handoff_4 as m

report = {"draft": {"post": "$QNT moved on verified market data.", "generation_mode": "NIC"}}
items = m.extract_candidates(report)
assert len(items) == 1
assert items[0]["script"].startswith("$QNT")

multi = {"candidate_scripts_4": [{"script": "angle one"}, {"text": "angle two"}]}
items = m.extract_candidates(multi)
assert [x["script"] for x in items] == ["angle one", "angle two"]

now = datetime.now(timezone.utc)
assert m.parse_dt(now.isoformat()) is not None
assert m.parse_dt((now - timedelta(minutes=1)).isoformat()) < now
print("NIC candidate handoff tests: PASS")
