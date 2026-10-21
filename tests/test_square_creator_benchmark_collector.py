import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src import square_creator_benchmark_collector as collector


class SquareCreatorBenchmarkTests(unittest.TestCase):
    def test_walk_posts_extracts_public_post_and_caps_excerpt(self):
        payload = {"data": [{"postId": "12345", "content": "A useful market explanation " * 40,
                             "authorName": "PublicCreator", "viewCount": 100,
                             "likeCount": 5, "commentCount": 2, "shareCount": 1}]}
        found = {}
        collector.walk_posts(payload, found)
        self.assertIn("12345", found)
        self.assertLessEqual(len(collector.text_value(found["12345"])), collector.MAX_TEXT)

    def test_engagement_rate_requires_visible_views(self):
        self.assertIsNone(collector.engagement_rate({"views": 0, "likes": 4}))
        self.assertAlmostEqual(collector.engagement_rate({"views": 100, "likes": 4, "replies": 2, "shares": 1}), 0.11)

    def test_creator_benchmark_requires_three_posts_and_never_claims_earnings(self):
        rows = [
            {"creator": "A", "creator_id": "u1", "views": 100, "likes": 10, "replies": 1, "shares": 0, "source_url": f"https://x/{i}"}
            for i in range(3)
        ]
        rows += [{"creator": "B", "creator_id": "u2", "views": 100, "likes": 99, "replies": 0, "shares": 0, "source_url": "https://x/b"}]
        report = collector.build_benchmark(rows, "2026-10-17T00:00:00+00:00")
        self.assertEqual(len(report["creator_benchmarks"]), 1)
        self.assertEqual(report["creator_benchmarks"][0]["creator_id"], "u1")
        self.assertEqual(report["creator_benchmarks"][0]["earnings_status"], "NOT_PUBLICLY_VERIFIED")
        self.assertFalse(report["earnings_policy"]["creator_income_inferred_from_views"])

    def test_posted_at_normalizes_seconds_milliseconds_and_unknown_dates(self):
        seconds = 1790000000
        self.assertIsNotNone(collector.posted_at({"createTime": seconds}))
        self.assertIsNotNone(collector.posted_at({"publishedAt": seconds * 1000}))
        self.assertIsNone(collector.posted_at({"createTime": "not-a-date"}))

    def test_posted_at_finds_nested_and_alternate_public_feed_timestamp_fields(self):
        nested = {"data": {"post": {"publishedTime": "2026-10-20T10:30:00Z"}}}
        millis = {"meta": {"releaseTime": 1792492200000}}
        self.assertEqual(collector.posted_at(nested), "2026-10-20T10:30:00+00:00")
        self.assertIsNotNone(collector.posted_at(millis))
        self.assertIsNone(collector.posted_at({"author": {"lastActiveTime": 1792492200000}}))

    def test_rolling_windows_use_real_post_dates_and_multiple_creator_posts(self):
        now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        rows = [
            {"creator": "A", "creator_id": "a", "posted_at": now.isoformat(), "archetype": "education_explainer", "views": 100, "likes": 10, "replies": 4, "shares": 2, "source_url": "https://x/" + str(i)}
            for i in range(3)
        ]
        rows += [
            {"creator": "B", "creator_id": "b", "posted_at": (now - timedelta(days=10)).isoformat(), "archetype": "technical_chart", "views": 200, "likes": 8, "replies": 2, "shares": 1, "source_url": "https://y/" + str(i)}
            for i in range(3)
        ]
        rows += [{"creator": "Undated", "creator_id": "u", "views": 9999, "likes": 999, "replies": 99, "shares": 99}]
        report = collector.build_benchmark(rows, now.isoformat())
        seven = report["rolling_learning_windows"]["seven_day"]
        fourteen = report["rolling_learning_windows"]["fourteen_day"]
        self.assertEqual(seven["dated_posts"], 3)
        self.assertEqual(fourteen["dated_posts"], 6)
        self.assertEqual(seven["creator_candidates"][0]["creator_id"], "a")
        self.assertEqual(fourteen["earnings_status"], "PUBLIC_METRICS_ONLY_NOT_EARNINGS")
        self.assertNotIn("u", [x["creator_id"] for x in fourteen["creator_candidates"]])

    def test_run_preserves_existing_examples_and_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples, out, report, state = [root / name for name in ("examples.json", "out.json", "report.json", "state.json")]
            examples.write_text(json.dumps([{"source_type": "our_account_baseline", "text": "preserve me"}]), encoding="utf-8")
            with patch.object(collector, "EXAMPLES", examples), patch.object(collector, "OUT", out), patch.object(collector, "REPORT", report), patch.object(collector, "STATE", state), patch.object(collector, "fetch_public_posts", return_value=([{"post_id": "abc", "creator": "C", "text": "public excerpt", "source_url": "https://www.binance.com/en/square/post/abc"}], ["url"])):
                self.assertEqual(collector.main(), 0)
            saved = json.loads(examples.read_text(encoding="utf-8"))
            self.assertEqual(len(saved), 2)
            summary = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(summary["earnings_claims_verified"], 0)



    def test_metric_history_keeps_latest_daily_snapshot_and_drops_expired_rows(self):
        now = "2026-10-21T12:00:00+00:00"
        existing = [
            {"observation_date": "2026-09-01", "observed_at": "2026-09-01T12:00:00+00:00", "post_id": "expired", "views": 999},
            {"observation_date": "2026-10-21", "observed_at": "2026-10-21T08:00:00+00:00", "post_id": "123456", "views": 100},
        ]
        fresh = [
            {"post_id": "123456", "creator": "A", "creator_id": "a", "posted_at": "2026-10-20T10:00:00+00:00",
             "source_url": "https://www.binance.com/en/square/post/123456", "archetype": "education_explainer",
             "views": 250, "likes": 20, "replies": 3, "shares": 1, "format": "text"},
            {"post_id": "234567", "creator": "B", "creator_id": "b", "posted_at": "2026-10-20T11:00:00+00:00",
             "source_url": "https://www.binance.com/en/square/post/234567", "archetype": "technical_chart",
             "views": 50, "likes": 2, "replies": 0, "shares": 0, "format": "text"},
        ]
        history = collector.update_metric_history(existing, fresh, now)
        self.assertEqual(len(history), 2)
        self.assertEqual(next(row for row in history if row["post_id"] == "123456")["views"], 250)
        self.assertNotIn("expired", [row["post_id"] for row in history])

    def test_metric_history_reports_creator_growth_only_after_repeated_observations(self):
        history = []
        for day, views in (("2026-10-19", 100), ("2026-10-20", 150), ("2026-10-21", 225)):
            for index in range(3):
                history.append({
                    "post_id": f"12345{index}", "creator": "A", "creator_id": "a",
                    "archetype": "education_explainer", "observed_at": day + "T12:00:00+00:00",
                    "views": views + index, "likes": views // 10, "replies": index, "shares": 1,
                })
        result = collector._snapshot_trajectory(history, 7, "2026-10-21T13:00:00+00:00")
        self.assertEqual(result["posts_with_repeat_observations"], 3)
        self.assertEqual(result["by_creator"][0]["creator"], "A")
        self.assertGreater(result["by_creator"][0]["avg_views_growth"], 0)
        self.assertEqual(result["earnings_status"], "PUBLIC_METRIC_TRAJECTORY_NOT_EARNINGS")

    def test_fourteen_day_window_exposes_missing_older_week_coverage(self):
        now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        rows = [
            {"creator": "A", "creator_id": "a", "posted_at": (now - timedelta(days=age)).isoformat(),
             "archetype": "education_explainer", "views": 100, "likes": 10, "replies": 4,
             "shares": 2, "source_url": "https://x/" + str(age)}
            for age in (1, 2, 3)
        ]
        report = collector.build_benchmark(rows, now.isoformat())
        self.assertEqual(report["rolling_learning_windows"]["fourteen_day"]["coverage"]["posts_age_8_to_14_days"], 0)
        self.assertEqual(report["rolling_learning_windows"]["fourteen_day"]["coverage"]["status"], "NO_DISTINCT_POSTS_IN_DAYS_8_TO_14")

    def test_daily_collector_scans_deep_enough_for_two_week_research(self):
        self.assertGreaterEqual(collector.MAX_PAGES, 50)
        self.assertGreaterEqual(collector.MAX_EXAMPLES, 5000)
        self.assertGreaterEqual(collector.HISTORY_DAYS, 14)



if __name__ == "__main__":
    unittest.main()
