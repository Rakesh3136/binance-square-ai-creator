import importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("resolver",ROOT/"src/nic_forecast_outcome_resolver.py")
resolver=importlib.util.module_from_spec(spec); spec.loader.exec_module(resolver)

def test_unresolved_not_trusted():
    rows=[{"resolved":True,"side":"BULLISH","feature":"trend_aligned","regime":"TREND_UP","hit":True,"signed_return":1} for _ in range(29)]
    original=resolver.MATRIX
    try:
        resolver.MATRIX=ROOT/"data/live/_test_predictivity_matrix.json"
        resolver.rebuild(rows)
        assert list(json.loads(resolver.MATRIX.read_text())["matrix"].values())[0]["trusted"] is False
    finally:
        try: resolver.MATRIX.unlink()
        except FileNotFoundError: pass
        resolver.MATRIX=original
