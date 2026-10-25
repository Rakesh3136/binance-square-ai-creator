import importlib.util
from datetime import datetime, timedelta, timezone
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



def test_market_snapshot_freshness_fails_closed_for_missing_or_old_timestamps():
    now = datetime.now(timezone.utc)
    assert engine.snapshot_age_seconds({"generated_at": now.isoformat()}, now=now) == 0
    old = (now - timedelta(minutes=16)).isoformat()
    assert engine.snapshot_age_seconds({"generated_at": old}, now=now) == 16 * 60
    assert engine.snapshot_age_seconds({}, now=now) is None


def test_market_observation_score_requires_multiple_real_fields():
    complete = {
        "last_price": 100,
        "quote_volume_usdt": 1000000,
        "price_change_percent": 2.5,
        "intraday_range_percent": 4.0,
        "candles_1h": [{"close": i + 1} for i in range(6)],
    }
    assert engine.market_observation_score(complete) == 100
    assert engine.market_observation_score({"last_price": 100}) == 25
