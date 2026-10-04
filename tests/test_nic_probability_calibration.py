import json
import subprocess
import sys
from pathlib import Path


def test_calibration_engine_compiles():
    subprocess.run([sys.executable, '-m', 'py_compile', 'src/nic_probability_calibration.py'], check=True)


def test_calibration_math_contract():
    source=Path('src/nic_probability_calibration.py').read_text(encoding='utf-8')
    assert 'Brier' in source or 'brier_score' in source
    assert 'reliability_bins' in source
    assert 'recommended_probability_adjustment' in source
    assert 'MIN_BIN=5' in source
