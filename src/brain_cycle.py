"""Run the expandable knowledge/repair feedback cycle."""
from __future__ import annotations
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for script in ('knowledge_brain.py','repair_learning_bridge.py','living_brain.py'):
 p=subprocess.run(['python',f'src/{script}'],cwd=ROOT,text=True)
 if p.returncode!=0: raise SystemExit(p.returncode)
print('BRAIN_CYCLE_OK')
