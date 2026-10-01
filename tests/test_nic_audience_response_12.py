import json,tempfile
from pathlib import Path
import sys
sys.path.insert(0,"src")
import nic_audience_response_12 as m

assert m.similarity("Bitcoin breaks above resistance with volume","Bitcoin breaks above resistance with volume") == 1.0
assert m.similarity("macro inflation shock","banana recipe") < 0.2
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/"x.jsonl"
    p.write_text(json.dumps({"title":"same thesis volume resistance"})+"\n"+json.dumps({"title":"same thesis volume resistance"})+"\n")
    assert len(m.rows(p))==2
print("NIC 12 tests: PASS")
