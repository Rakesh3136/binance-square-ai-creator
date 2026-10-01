import json
from pathlib import Path
import tempfile,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
src=ROOT/"src/nic_post_publication_outcome_14.py"

def test_syntax():
    subprocess.run([sys.executable,"-m","py_compile",str(src)],check=True)

def test_exact_pid_helper():
    ns={"__file__":str(src),"__name__":"nic_post_publication_outcome_14_test"}
    exec(src.read_text(encoding="utf-8"),ns)
    assert ns["pid"]({"post_id":"12345"})=="12345"
    assert ns["pid"]({"post_id":"https://www.binance.com/en/square/post/ABC_9"})=="abc_9"

def test_numeric_unknown():
    ns={"__file__":str(src),"__name__":"nic_post_publication_outcome_14_test"}
    exec(src.read_text(encoding="utf-8"),ns)
    assert ns["num"]("12.5")==12.5
    assert ns["num"]("unknown") is None

if __name__=="__main__":
    test_syntax(); test_exact_pid_helper(); test_numeric_unknown()
    print(json.dumps({"status":"PASS","tests":3}))
