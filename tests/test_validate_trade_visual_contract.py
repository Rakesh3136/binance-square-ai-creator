import json, tempfile
from pathlib import Path
import sys
sys.path.insert(0,"src")
import validate_trade_visual_contract as m
with tempfile.TemporaryDirectory() as d:
    root=Path(d)
print("visual contract validator import: PASS")
