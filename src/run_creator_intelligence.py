import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=['audience_intelligence.py','market_timing.py','experiment_engine.py','visual_intelligence.py','thesis_ledger.py','creator_evolution.py','creator_brain.py','creator_brain_gate.py']
def main():
 for name in SCRIPTS:
  subprocess.run(['python',str(ROOT/'src'/name)],cwd=ROOT,check=True)
if __name__=='__main__': main()
