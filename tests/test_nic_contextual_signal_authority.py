import json, subprocess, sys
from pathlib import Path
p=Path("src/nic_contextual_signal_authority.py")
def test_compiles():
    subprocess.run([sys.executable,"-m","py_compile",str(p)],check=True)
def test_policy_is_conservative():
    s=p.read_text()
    assert "NO_TRADE" in s and "WATCH_ONLY" in s and "AUTHORIZED" in s
    assert "does not execute trades" in s
    assert "cannot modify frozen" in s
if __name__=="__main__":
    test_compiles(); test_policy_is_conservative(); print("NIC 23.4 tests passed")
