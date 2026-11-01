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

# A malformed free-form topic or non-ASCII display name must never become a
# Binance market symbol and must not reach Script Director as an authoritative ticker.
assert freeze.symbol({"topic": "牛来"}) == ""
assert freeze.symbol({"symbol": "牛来"}) == ""
assert freeze.symbol({"symbol": "QNT"}) == "QNTUSDT"
assert freeze.symbol({"symbol": "BINANCE:QNTUSDT"}) == "QNTUSDT"

invalid_signal = {
    "publish": True,
    "decision": "EDITORIAL_SIGNAL",
    "selected": {
        "symbol": "牛来",
        "topic": "牛来",
        "category": "research_insight",
        "editorial_only": True,
    },
}
assert freeze.signal_candidate(invalid_signal, portfolio, ignore_portfolio_allowlist=True) is None
recovery_pool = freeze.candidate_pool(
    portfolio,
    {},
    {},
    {"top_losers": [{"symbol": "QNTUSDT", "category": "top_losers"}]},
    invalid_signal,
    stale_portfolio=True,
)
assert any(freeze.symbol(row) == "QNTUSDT" for row in recovery_pool)

print("STALE_PORTFOLIO_SIGNAL_RECOVERY=PASS")
