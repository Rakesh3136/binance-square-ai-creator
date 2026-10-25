import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("original_research_engine", ROOT / "src" / "original_research_engine.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


def test_rows_excludes_stale_symbols_before_candidate_limit():
    market = {
        "top_content_signals": [
            {"symbol": "DELISTEDUSDT", "last_price": 1},
            {"symbol": "BTCUSDT", "last_price": 60000},
            {"symbol": "ETHUSDT", "last_price": 3000},
        ],
        "top_gainers": [],
        "top_losers": [],
        "highest_volume": [],
        "new_listing_market": [],
    }
    result = engine.rows(market, {"BTC", "ETH"})
    assert [row["symbol"] for row in result] == ["BTCUSDT", "ETHUSDT"]


def test_rows_preserves_legacy_behavior_without_universe_filter():
    market = {"top_content_signals": [{"symbol": "OLDUSDT", "last_price": 1}]}
    assert len(engine.rows(market)) == 1
