"""Regression tests for creator-period and 14-day lookback studies."""
import unittest
from datetime import datetime, timezone

from src.nic_weekly_earner_study import study


class WeeklyEarnerLookbackTests(unittest.TestCase):
    def test_reports_exact_period_and_14_day_posts_separately(self):
        obs = {"entries": [{
            "status": "VERIFIED_FIRST_PARTY_DISPLAYED_EARNINGS",
            "creator": "Creator", "creator_profile_url": "https://www.binance.com/en/square/profile/creator",
            "displayed_amount": 250, "currency": "USDC", "rank": 1,
            "period_start": "2026-10-12T00:00:00Z", "period_end": "2026-10-19T00:00:00Z",
            "source_url": "https://www.binance.com/en/square/WriteToEarn", "evidence_ref": "test-fixture"
        }]}
        research = {"posts": [
            {"creator_profile_url": "https://www.binance.com/en/square/profile/creator",
             "posted_at": "2026-10-06T12:00:00Z", "post_id": "old", "archetype": "analysis", "format": "text"},
            {"creator_profile_url": "https://www.binance.com/en/square/profile/creator",
             "posted_at": "2026-10-15T12:00:00Z", "post_id": "week", "archetype": "story", "format": "image"},
            {"creator_profile_url": "https://www.binance.com/en/square/profile/creator",
             "posted_at": "2026-10-21T12:00:00Z", "post_id": "future", "archetype": "noise", "format": "video"}
        ]}
        result = study(obs, research, datetime(2026, 10, 24, tzinfo=timezone.utc))
        item = result["studies"][0]
        self.assertEqual(item["exact_earnings_period"]["post_count"], 1)
        self.assertEqual(item["fourteen_day_lookback"]["post_count"], 2)
        self.assertEqual(result["creator_periods_with_14_day_posts"], 1)
        self.assertFalse(item["individual_post_reward_attribution"])
        self.assertNotIn("future", [p["post_id"] for p in item["fourteen_day_lookback"]["posts"]])


if __name__ == "__main__":
    unittest.main()
