import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from src.nic_square_profile_research import (
    build_candidates, profile_username, post_id_from_url, research_profiles, _parse_profile_post,
)

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


class SquareProfileResearchTests(unittest.TestCase):
    def test_only_official_profile_urls_and_public_post_urls_are_accepted(self):
        self.assertEqual(profile_username("https://www.binance.com/en/square/profile/Alpha"), "Alpha")
        self.assertIsNone(profile_username("https://example.com/en/square/profile/Alpha"))
        self.assertEqual(post_id_from_url("https://www.binance.com/en/square/post/123456"), "123456")
        self.assertIsNone(post_id_from_url("https://example.com/en/square/post/123456"))

    def test_candidate_queue_prioritizes_observed_leaderboard_and_deduplicates_handles(self):
        candidates = build_candidates(
            examples=[{"creator": "Report", "posted_at": "2026-10-20T10:00:00Z", "text": "Write to Earn leaderboard @Alpha - $800 USDC", "source_url": "https://www.binance.com/en/square/post/123"}],
            benchmark={"creator_benchmarks": [{"creator": "Alpha", "sample_urls": ["https://www.binance.com/en/square/post/456"]}, {"creator": "Beta", "sample_urls": ["https://www.binance.com/en/square/post/789"]}]},
            observed={"entries": [{"creator": "Alpha", "creator_profile_url": "https://www.binance.com/en/square/profile/Alpha", "displayed_amount": 900, "currency": "USDC"}]},
            now=NOW, limit=10,
        )
        self.assertEqual(candidates[0]["discovery_source"], "observed_write_to_earn_leaderboard")
        self.assertEqual(sum(1 for c in candidates if (c.get("username") or c["creator"]).casefold() == "alpha"), 1)
        self.assertEqual(candidates[0]["earnings_status"], "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT")
        self.assertEqual(next(c for c in candidates if c["creator"] == "Alpha")["username"], "Alpha")

    def test_daily_rotation_changes_benchmark_creator_batch_but_keeps_leads_first(self):
        benchmark = {"creator_benchmarks": [
            {"creator": f"Creator{i:02d}", "sample_urls": [f"https://www.binance.com/en/square/post/{10000+i}"], "mean_public_engagement_rate": 0.1}
            for i in range(30)
        ]}
        one = build_candidates([], benchmark, {"entries": []}, datetime(2026, 10, 21, 12, tzinfo=timezone.utc), limit=5)
        two = build_candidates([], benchmark, {"entries": []}, datetime(2026, 10, 22, 12, tzinfo=timezone.utc), limit=5)
        self.assertEqual(len(one), 5)
        self.assertEqual(len(two), 5)
        self.assertNotEqual([x["creator"] for x in one], [x["creator"] for x in two])
        lead_benchmark = {"creator_benchmarks": benchmark["creator_benchmarks"]}
        observed = {"entries": [{"creator": "VerifiedLead", "creator_profile_url": "https://www.binance.com/en/square/profile/VerifiedLead", "displayed_amount": 500, "currency": "USDC"}]}
        selected = build_candidates([], lead_benchmark, observed, datetime(2026, 10, 21, 12, tzinfo=timezone.utc), limit=5)
        self.assertEqual(selected[0]["creator"], "VerifiedLead")
        self.assertEqual(len(selected), 5)

    def test_suspicious_comment_counters_are_unknown_not_used_as_engagement(self):
        profile = {"creator": "Alpha", "username": "Alpha", "square_uid": "uid-alpha",
                   "creator_profile_url": "https://www.binance.com/en/square/profile/Alpha"}
        suspicious = _parse_profile_post({
            "id": "bad-count", "createTime": int(NOW.timestamp() * 1000) - 3600_000,
            "bodyTextOnly": "An educational post discussing liquidity and market structure.",
            "viewCount": 431, "likeCount": 20, "commentCount": 431, "shareCount": 4,
        }, profile, NOW)
        absent = _parse_profile_post({
            "id": "no-comments", "createTime": int(NOW.timestamp() * 1000) - 3600_000,
            "bodyTextOnly": "Another educational post discussing volume and market structure.",
            "viewCount": 200, "likeCount": 5, "shareCount": 1,
        }, profile, NOW)
        genuine_zero = _parse_profile_post({
            "id": "zero-comments", "createTime": int(NOW.timestamp() * 1000) - 3600_000,
            "bodyTextOnly": "An original post about risk and portfolio construction.",
            "viewCount": 200, "likeCount": 5, "commentCount": 0, "shareCount": 1,
        }, profile, NOW)
        self.assertIsNone(suspicious["replies"])
        self.assertEqual(suspicious["reply_metric_status"], "SUSPICIOUS_COUNTER_EQUALS_OR_EXCEEDS_VIEWS")
        self.assertFalse(suspicious["replies_observed"])
        self.assertIsNone(absent["replies"])
        self.assertEqual(absent["reply_metric_status"], "MISSING_COUNTER")
        self.assertEqual(genuine_zero["replies"], 0)
        self.assertEqual(genuine_zero["reply_metric_status"], "OBSERVED")

    def test_profile_research_uses_public_post_and_profile_endpoints_and_counts_7_14_day_windows(self):
        def fake_request(url, method="GET", payload=None, timeout=15.0):
            if "/special/content/detail/456" in url:
                return {"code": "000000", "data": {"squareAuthorId": "uid-alpha", "username": "Alpha", "displayName": "Alpha"}}
            if url.endswith("/friendly/pgc/user/client") and method == "POST":
                user = (payload or {})
                return {"code": "000000", "data": {"squareUid": user.get("squareUid", "uid-alpha"), "username": "Alpha", "displayName": "Alpha", "totalFollowerCount": 42, "userShareLink": "https://www.binance.com/en/square/profile/Alpha"}}
            if "/queryUserProfilePageContentsWithFilter" in url:
                return {"code": "000000", "data": {
                    "contents": [
                        {"id": "p7", "createTime": int(NOW.timestamp() * 1000) - 2 * 86400 * 1000,
                         "bodyTextOnly": "An original educational explanation of market liquidity and risk.", "viewCount": 100, "likeCount": 6, "commentCount": 2, "shareCount": 1},
                        {"id": "p10", "createTime": int(NOW.timestamp() * 1000) - 10 * 86400 * 1000,
                         "bodyTextOnly": "A second original educational post explains market structure and volume.", "viewCount": 200, "likeCount": 5, "commentCount": 1, "shareCount": 0},
                    ],
                    "timeOffset": 0, "isExistSecondPage": False,
                }}
            return {"code": "000000", "data": {}}
        with patch("src.nic_square_profile_research.time.sleep", return_value=None):
            report = research_profiles([{"creator": "Alpha", "sample_urls": ["https://www.binance.com/en/square/post/456"]}], NOW, fake_request, lambda _: None)
        self.assertEqual(report["status"], "PROFILE_RESEARCH_COMPLETE")
        self.assertEqual(report["profiles_resolved"], 1)
        self.assertEqual(report["posts_collected_7d"], 1)
        self.assertEqual(report["posts_collected_8_to_14d"], 1)
        self.assertTrue(report["public_metrics_are_not_earnings"])
        self.assertFalse(report["authenticated_session_used"])

    def test_endpoint_failures_are_reported_and_do_not_fake_a_creator_or_posts(self):
        def blocked(*args, **kwargs):
            raise PermissionError("blocked")
        report = research_profiles([{"creator": "Alpha", "username": "Alpha"}], NOW, blocked, lambda _: None)
        self.assertEqual(report["status"], "PUBLIC_PROFILE_ENDPOINT_BLOCKED")
        self.assertEqual(report["profiles_resolved"], 0)
        self.assertEqual(report["posts_collected_14d"], 0)
        self.assertEqual(report["failures"][0]["status"], "PROFILE_RESOLUTION_BLOCKED_RuntimeError")


if __name__ == "__main__":
    unittest.main()
