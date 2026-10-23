"""Tests for period-level weekly earner research."""
import unittest
from datetime import datetime, timezone
from src.nic_weekly_earner_study import study

class Tests(unittest.TestCase):
    def test_empty_input_is_explicit(self):
        r = study({"entries": []}, {"posts": []}, datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(r["status"], "NO_VALID_WEEKLY_EARNER_OBSERVATIONS")
        self.assertEqual(r["studies"], [])

    def test_period_match_is_not_post_reward_attribution(self):
        entry = {"creator":"Creator", "creator_profile_url":"https://www.binance.com/en/square/profile/example",
        "displayed_amount":800, "currency":"USDC", "period_start":"2026-10-12T00:00:00Z",
        "period_end":"2026-10-19T00:00:00Z", "source_url":"https://www.binance.com/en/square/creator-center/data",
        "evidence_ref":"row-1", "status":"VERIFIED_FIRST_PARTY_DISPLAYED_EARNINGS"}
        posts = [{"creator_profile_url":"https://www.binance.com/en/square/profile/example",
        "posted_at":"2026-10-14T10:00:00Z","archetype":"analysis","format":"text"},
        {"creator_profile_url":"https://www.binance.com/en/square/profile/example",
        "posted_at":"2026-10-20T10:00:00Z","archetype":"news","format":"text"}]
        r = study({"entries":[entry]}, {"posts":posts}, datetime(2026,10,23,tzinfo=timezone.utc))
        row = r["studies"][0]
        self.assertEqual(row["posts_found_in_earnings_period"], 1)
        self.assertFalse(row["individual_post_reward_attribution"])

if __name__ == "__main__":
    unittest.main()
