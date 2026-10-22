import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("binance_square_publisher.py")
SPEC = importlib.util.spec_from_file_location("nic_publisher_story_test", MODULE_PATH)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class StoryDeduplicationTests(unittest.TestCase):
    def test_normalizes_price_refreshes_from_same_btc_headline(self):
        first = "🚨 $BTC: Stablecoin wallets challenge traditional bank accounts as main consumer money hub"
        refreshed = "🚨 $BTC: Stablecoin wallets challenge traditional bank accounts as main consumer money hub"
        self.assertEqual(
            publisher.normalized_story_headline(first),
            publisher.normalized_story_headline(refreshed),
        )
        self.assertGreaterEqual(len(publisher.normalized_story_headline(first).split()), 4)

    def test_blocks_same_story_id_even_if_asset_or_category_changes(self):
        now = datetime.now(timezone.utc)
        row = {
            "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
            "published_at": (now - timedelta(days=2)).isoformat(),
            "post_id": "123456",
            "link": "https://www.binance.com/square/post/123456",
            "story_id": "stablecoin-wallets-vs-banks",
            "symbol": "BTC",
            "category": "news_and_macro",
            "text": "Stablecoin wallets challenge traditional bank accounts as main consumer money hub",
        }
        with patch.object(publisher, "recent_rows", return_value=[row]):
            reason, existing = publisher.story_duplicate_match(
                "A different summary of the same event.",
                {"story_id": "stablecoin-wallets-vs-banks", "category": "news_and_macro", "symbol": "ETH"},
                {"symbol": "ETH", "category": "news_and_macro"},
                {"story_id": ""},
                {},
            )
        self.assertEqual(reason, "same_story_id_within_14d")
        self.assertEqual(existing["post_id"], "123456")

    def test_blocks_same_normalized_news_headline_when_price_changes(self):
        now = datetime.now(timezone.utc)
        old = {
            "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
            "published_at": (now - timedelta(days=1)).isoformat(),
            "post_id": "123456",
            "link": "https://www.binance.com/square/post/123456",
            "symbol": "BTC",
            "category": "news_and_macro",
            "text": "🚨 $BTC: Stablecoin wallets challenge traditional bank accounts as main consumer money hub",
        }
        with patch.object(publisher, "recent_rows", return_value=[old]):
            reason, existing = publisher.story_duplicate_match(
                "🚨 $BTC: Stablecoin wallets challenge traditional bank accounts as main consumer money hub\n\nBTC is now up 1.2% with $2.1B volume.",
                {"category": "news_and_macro"},
                {"category": "news_and_macro"},
                {},
                {},
            )
        self.assertEqual(reason, "same_normalized_news_headline_within_14d")
        self.assertEqual(existing["post_id"], "123456")

    def test_allows_a_distinct_news_headline(self):
        now = datetime.now(timezone.utc)
        old = {
            "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
            "published_at": (now - timedelta(days=1)).isoformat(),
            "post_id": "123456",
            "symbol": "BTC",
            "category": "news_and_macro",
            "text": "🚨 $BTC: Stablecoin wallets challenge traditional bank accounts as main consumer money hub",
        }
        with patch.object(publisher, "recent_rows", return_value=[old]):
            reason, existing = publisher.story_duplicate_match(
                "🚨 $BTC: Bitcoin miners expand renewable energy capacity across Texas",
                {"category": "news_and_macro"},
                {"category": "news_and_macro"},
                {},
                {},
            )
        self.assertEqual(reason, "")
        self.assertIsNone(existing)


if __name__ == "__main__":
    unittest.main()
