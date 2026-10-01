import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/nic_creative_learning_15.py"
def run():
    subprocess.run([sys.executable,"-m","py_compile",str(SRC)],check=True)
if __name__=="__main__":
    run(); print(json.dumps({"status":"PASS","tests":1}))
