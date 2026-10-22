"""Regression tests for authoritative market-item lookup coverage."""
import unittest

from src.content_integrity_gate_4 import find_market_item


class FindMarketItemTests(unittest.TestCase):
    def test_finds_news_asset_outside_ranked_leaderboards(self):
        market = {
            "top_content_signals": [{"symbol": "BTCUSDT", "last_price": 100}],
            "top_gainers": [],
            "top_losers": [],
            "highest_volume": [],
            "new_listing_market": [],
            "all_market_symbols": [{"symbol": "ADAUSDT", "last_price": 0.42, "price_change_percent": 1.2}],
        }
        self.assertEqual(find_market_item(market, "ADA"), market["all_market_symbols"][0])

    def test_preserves_fail_closed_when_symbol_is_absent(self):
        market = {"top_content_signals": [{"symbol": "BTCUSDT", "last_price": 100}], "all_market_symbols": []}
        self.assertIsNone(find_market_item(market, "ADA"))

    def test_legacy_snapshots_still_search_ranked_groups(self):
        item = {"symbol": "ADAUSDT", "last_price": 0.42}
        self.assertIs(find_market_item({"top_gainers": [item]}, "ADA"), item)


if __name__ == "__main__":
    unittest.main()
