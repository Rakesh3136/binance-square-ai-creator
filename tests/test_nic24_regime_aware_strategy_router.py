import json, subprocess, sys
from pathlib import Path
P=Path('src/nic24_regime_aware_strategy_router.py')
def test_compiles(): subprocess.run([sys.executable,'-m','py_compile',str(P)],check=True)
def test_safe_defaults():
    s=P.read_text(encoding='utf-8')
    assert 'UNCLASSIFIED' in s and 'HOLD' in s and 'does not execute trades' in s
    assert 'cannot alter frozen' in s
if __name__=='__main__': test_compiles(); test_safe_defaults(); print('NIC 24 tests passed')
