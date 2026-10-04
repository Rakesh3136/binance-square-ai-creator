import subprocess,sys
from pathlib import Path

P=Path("src/nic24_1_strategy_content_router.py")

def test_compiles():
    subprocess.run([sys.executable,"-m","py_compile",str(P)],check=True)

def test_contract():
    s=P.read_text(encoding="utf-8")
    for term in ("NIC-24.1-STRATEGY-CONTENT-ROUTER","repeat_penalty","content_format","chart_style","cannot modify entry"):
        assert term in s

if __name__=="__main__":
    test_compiles()
    test_contract()
    print("NIC 24.1 tests passed")
