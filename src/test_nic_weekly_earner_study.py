"""Tests for period-level weekly earner research and the separate 14-day pre-period."""
import unittest
from datetime import datetime, timezone
from nic_weekly_earner_study import study

ENTRY = {
    "creator": "Creator",
    "creator_profile_url": "https://www.binance.com/en/square/profile/example",
    "displayed_amount": 800,
    "currency": "USDC",
    "period_start": "2026-10-12T00:00:00Z",
    "period_end": "2026-10-19T00:00:00Z",
    "source_url": "https://www.binance.com/en/square/WriteToEarn",
    "evidence_ref": "row-1",
    "status": "VERIFIED_FIRST_PARTY_DISPLAYED_EARNINGS",
}
PROFILE = {
    "creator": "Creator",
    "creator_profile_url": ENTRY["creator_profile_url"],
    "observed_display_name": "Creator",
    "identity_match": "verified",
    "profile_resolution_status": "VERIFIED_PUBLIC_PROFILE_IDENTITY",
    "window_7d_complete": True,
    "window_pre_period_14d_complete": True,
}


class Tests(unittest.TestCase):
    def test_empty_input_is_explicit(self):
        result = study({"entries": []}, {"posts": [], "profiles": []},
                       datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "NO_VALID_WEEKLY_EARNER_OBSERVATIONS")
        self.assertEqual(result["studies"], [])

    def test_exact_reward_period_and_preceding_14_days_are_separate(self):
        posts = [
            {"creator_profile_url": ENTRY["creator_profile_url"],
             "posted_at": "2026-10-14T10:00:00Z", "archetype": "analysis", "format": "text"},
            {"creator_profile_url": ENTRY["creator_profile_url"],
             "posted_at": "2026-10-05T10:00:00Z", "archetype": "education", "format": "article"},
            {"creator_profile_url": ENTRY["creator_profile_url"],
             "posted_at": "2026-10-20T10:00:00Z", "archetype": "news", "format": "text"},
        ]
        result = study({"entries": [ENTRY]}, {"posts": posts, "profiles": [PROFILE]},
                       datetime(2026, 10, 23, tzinfo=timezone.utc))
        row = result["studies"][0]
        self.assertEqual(result["status"], "WEEKLY_EARNER_STUDY_READY")
        self.assertEqual(row["posts_found_in_earnings_period"], 1)
        self.assertEqual(row["pre_period_14_day_history"]["post_count"], 1)
        self.assertEqual(row["fourteen_day_lookback"]["post_count"], 2)
        self.assertTrue(row["profile_identity_verified"])
        self.assertFalse(row["individual_post_reward_attribution"])
        self.assertTrue(result["policy"]["does_not_infer_per_post_earnings"])

    def test_sparse_or_unproven_pre_period_coverage_is_partial_not_ready(self):
        profile = dict(PROFILE, window_pre_period_14d_complete=False)
        posts = [{
            "creator_profile_url": ENTRY["creator_profile_url"],
            "posted_at": "2026-10-14T10:00:00Z", "archetype": "analysis", "format": "text",
        }]
        result = study({"entries": [ENTRY]}, {"posts": posts, "profiles": [profile]},
                       datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "WEEKLY_EARNER_STUDY_PARTIAL")
        self.assertEqual(result["creator_periods_with_complete_pre_period_14d_coverage"], 0)
        self.assertFalse(result["studies"][0]["pre_period_14_day_history"]["coverage_complete"])

    def test_unverified_profile_identity_never_matches_posts(self):
        profile = dict(PROFILE, identity_match="unverified")
        posts = [{
            "creator_profile_url": ENTRY["creator_profile_url"],
            "posted_at": "2026-10-14T10:00:00Z", "archetype": "analysis", "format": "text",
        }]
        result = study({"entries": [ENTRY]}, {"posts": posts, "profiles": [profile]},
                       datetime(2026, 10, 23, tzinfo=timezone.utc))
        row = result["studies"][0]
        self.assertEqual(result["status"], "WEEKLY_EARNER_STUDY_PARTIAL")
        self.assertEqual(row["posts_found_in_earnings_period"], 0)
        self.assertEqual(row["exact_earnings_period"]["empty_history_reason"],
                         "PUBLIC_PROFILE_IDENTITY_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
