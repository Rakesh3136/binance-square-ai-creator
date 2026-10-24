"""Regression tests for exact leaderboard-period creator post coverage."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src import nic_square_profile_research as research


class CreatorPeriodCoverageTests(unittest.TestCase):
    def test_observed_weekly_reward_uses_its_exact_7_and_14_day_windows(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        candidate = {
            "creator": "Creator A",
            "username": "creator_a",
            "creator_profile_url": "https://www.binance.com/en/square/profile/creator_a",
            "discovery_source": "observed_write_to_earn_leaderboard",
            "period_start": "2026-10-12T00:00:00Z",
            "period_end": "2026-10-18T23:59:59Z",
        }
        posts = [
            {
                "post_id": "in-week",
                "creator": "Creator A",
                "creator_profile_url": candidate["creator_profile_url"],
                "source_url": "https://www.binance.com/en/square/post/in-week",
                "text": "Weekly post",
                "archetype": "evidence-led",
                "posted_at": "2026-10-13T10:00:00+00:00",
                "format": "text",
                "views": 10,
                "likes": 1,
                "replies": 0,
                "shares": 0,
            },
            {
                "post_id": "lookback",
                "creator": "Creator A",
                "creator_profile_url": candidate["creator_profile_url"],
                "source_url": "https://www.binance.com/en/square/post/lookback",
                "text": "Fourteen day lookback post",
                "archetype": "research",
                "posted_at": "2026-10-06T10:00:00+00:00",
                "format": "text",
                "views": 20,
                "likes": 2,
                "replies": 0,
                "shares": 0,
            },
        ]
        captured = {}

        def fake_fetch(uid, profile, current, request_json, sleep_fn, window_start, window_end):
            captured["start"] = window_start
            captured["end"] = window_end
            return posts, "PROFILE_POSTS_COMPLETE_WINDOW", 2

        resolved_profile = {
            "creator": "Creator A",
            "username": "creator_a",
            "display_name": "Creator A",
            "observed_display_name": "Creator A",
            "square_uid": "uid-1",
            "creator_profile_url": candidate["creator_profile_url"],
        }
        with patch.object(research, "_resolve_user", return_value=(resolved_profile, "uid-1")), patch.object(
            research, "_fetch_profile_posts", side_effect=fake_fetch
        ):
            result = research.research_profiles([candidate], now=now, sleep_fn=lambda _: None)

        self.assertEqual(captured["start"].isoformat(), "2026-10-05T00:00:00+00:00")
        self.assertEqual(captured["end"].isoformat(), "2026-10-18T23:59:59+00:00")
        creator = result["profiles"][0]
        self.assertTrue(creator["window_7d_complete"])
        self.assertTrue(creator["window_14d_complete"])
        self.assertEqual(creator["posts_7d"], 1)
        self.assertEqual(creator["posts_14d"], 2)
        self.assertEqual(creator["posts_age_8_to_14_days"], 1)
        self.assertTrue(result["leaderboard_7d_window_coverage_complete"])
        self.assertTrue(result["leaderboard_14d_window_coverage_complete"])
        self.assertEqual(result["coverage_status"], "FULL_7_AND_14_DAY_LEADERBOARD_COVERAGE")

    def test_empty_page_with_more_flag_is_partial_not_complete(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        def fake_request(url):
            return {"data": {"contents": [], "timeOffset": "next-cursor", "isExistSecondPage": True}}
        posts, status, pages = research._fetch_profile_posts(
            "uid-1", {"creator": "Creator A"}, now, request_json=fake_request,
            sleep_fn=lambda _: None,
            window_start=datetime(2026, 10, 5, tzinfo=timezone.utc),
            window_end=datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(posts, [])
        self.assertEqual(status, "PARTIAL_PROFILE_POSTS_EMPTY_PAGE_WITH_MORE")
        self.assertEqual(pages, 1)

    def test_empty_exhausted_page_without_window_boundary_is_not_complete(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        def fake_request(url):
            return {"data": {"contents": [], "timeOffset": 0, "isExistSecondPage": False}}
        posts, status, pages = research._fetch_profile_posts(
            "uid-1", {"creator": "Creator A"}, now, request_json=fake_request,
            sleep_fn=lambda _: None,
            window_start=datetime(2026, 10, 5, tzinfo=timezone.utc),
            window_end=datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(posts, [])
        self.assertEqual(status, "PARTIAL_PROFILE_POSTS_NO_WINDOW_BOUNDARY_EVIDENCE")
        self.assertEqual(pages, 1)

    def test_only_newer_posts_do_not_prove_a_historical_window_was_collected(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        def fake_request(url):
            return {"data": {"contents": [{
                "id": "newer-post",
                "createTime": int(datetime(2026, 10, 23, 10, tzinfo=timezone.utc).timestamp() * 1000),
                "bodyTextOnly": "This post is newer than the leaderboard reward period.",
            }], "timeOffset": 0, "isExistSecondPage": False}}
        posts, status, pages = research._fetch_profile_posts(
            "uid-1", {"creator": "Creator A"}, now, request_json=fake_request,
            sleep_fn=lambda _: None,
            window_start=datetime(2026, 10, 5, tzinfo=timezone.utc),
            window_end=datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(posts, [])
        self.assertEqual(status, "PARTIAL_PROFILE_POSTS_NO_WINDOW_BOUNDARY_EVIDENCE")
        self.assertEqual(pages, 1)

    def test_partial_pagination_never_claims_complete_coverage(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        candidate = {
            "creator": "Creator A",
            "discovery_source": "observed_write_to_earn_leaderboard",
            "period_start": "2026-10-12T00:00:00Z",
            "period_end": "2026-10-18T23:59:59Z",
        }
        profile = {
            "creator": "Creator A",
            "username": "creator_a",
            "display_name": "Creator A",
            "observed_display_name": "Creator A",
            "square_uid": "uid-1",
            "creator_profile_url": "https://www.binance.com/en/square/profile/creator_a",
        }
        with patch.object(research, "_resolve_user", return_value=(profile, "uid-1")), patch.object(
            research, "_fetch_profile_posts", return_value=([], "PARTIAL_PROFILE_POSTS_PAGE_LIMIT", 50)
        ):
            result = research.research_profiles([candidate], now=now, sleep_fn=lambda _: None)
        self.assertFalse(result["profiles"][0]["window_7d_complete"])
        self.assertFalse(result["leaderboard_7d_window_coverage_complete"])
        self.assertEqual(result["coverage_status"], "PARTIAL_OR_BLOCKED_LEADERBOARD_COVERAGE")


    def test_in_window_posts_without_crossing_start_boundary_remain_partial(self):
        now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
        def fake_request(url):
            return {"data": {"contents": [{
                "id": "in-window-post",
                "createTime": int(datetime(2026, 10, 13, 10, tzinfo=timezone.utc).timestamp() * 1000),
                "bodyTextOnly": "A valid dated post inside the requested historical window.",
            }], "timeOffset": 0, "isExistSecondPage": False}}
        posts, status, pages = research._fetch_profile_posts(
            "uid-1", {"creator": "Creator A"}, now, request_json=fake_request,
            sleep_fn=lambda _: None,
            window_start=datetime(2026, 10, 5, tzinfo=timezone.utc),
            window_end=datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc),
        )
        self.assertEqual(len(posts), 1)
        self.assertEqual(status, "PARTIAL_PROFILE_POSTS_NO_WINDOW_BOUNDARY_EVIDENCE")
        self.assertEqual(pages, 1)


if __name__ == "__main__":
    unittest.main()
