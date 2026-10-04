import subprocess,sys
from pathlib import Path

def test_compiles():
    subprocess.run([sys.executable,'-m','py_compile','src/nic24_regime_strategy_router.py'],check=True)

def test_has_safe_fallback():
    s=Path('src/nic24_regime_strategy_router.py').read_text()
    assert 'RESEARCH_ONLY' in s
    assert 'Never changes entry' in s
    assert 'Downstream authority' in s
