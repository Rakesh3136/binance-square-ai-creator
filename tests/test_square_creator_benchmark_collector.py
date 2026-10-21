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
        self.assertNotIn("u", str(fourteen["creator_candidates"]))

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


if __name__ == "__main__":
    unittest.main()
