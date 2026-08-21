import json
import os
from pathlib import Path

p = Path("data/live/editorial_preflight.json")
d = json.loads(p.read_text(encoding="utf-8"))
d["run_ai"] = True
d["reason"] = "manual_topic"
p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(d, indent=2, ensure_ascii=False))
