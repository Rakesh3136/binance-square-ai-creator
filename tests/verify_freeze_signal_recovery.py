import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freeze", ROOT / "src" / "freeze_opportunity.py")
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)

signal = {
    "publish": True,
    "decision": "EDITORIAL_SIGNAL",
    "selected": {
        "symbol": "QNT",
        "category": "research_insight",
        "editorial_only": True,
        "score": 96.3,
    },
}
portfolio = {
    "publish": True,
    "selected": {"symbol": "ICXUSDT"},
    "top_allowed_candidates": [{"candidate": {"symbol": "NEARUSDT"}}],
}

assert freeze.signal_candidate(signal, portfolio, ignore_portfolio_allowlist=False) is None
recovered = freeze.signal_candidate(signal, portfolio, ignore_portfolio_allowlist=True)
assert recovered is not None
assert recovered["symbol"] == "QNT"
assert recovered["signal_first_editorial"] is True

print("STALE_PORTFOLIO_SIGNAL_RECOVERY=PASS")
