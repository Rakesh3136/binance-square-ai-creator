"""Regression tests for period-aligned public creator-post collection."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from src import nic_square_profile_research as research


class HistoricalWindowCursorTests(unittest.TestCase):
    def test_collection_starts_at_requested_reward_period_end(self):
        now = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
        period_start = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)
        period_end = datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc)
        requested_urls = []

        def fake_request(url, method="GET", payload=None, timeout=15.0):
            requested_urls.append(url)
            return {
                "success": True,
                "data": {
                    "contents": [],
                    "timeOffset": None,
                    "isExistSecondPage": False,
                },
            }

        _, _, pages = research._fetch_profile_posts(
            uid="test-square-uid",
            profile={
                "creator": "Example Creator",
                "username": "example",
                "creator_profile_url": "https://www.binance.com/en/square/profile/example",
            },
            now=now,
            request_json=fake_request,
            sleep_fn=lambda _: None,
            window_start=period_start,
            window_end=period_end,
        )

        self.assertEqual(pages, 1)
        self.assertEqual(len(requested_urls), 1)
        query = parse_qs(urlparse(requested_urls[0]).query)
        self.assertEqual(
            int(query["timeOffset"][0]),
            int(period_end.timestamp() * 1000),
            "historical research must start at the reward window end, not today's time",
        )
        self.assertNotEqual(int(query["timeOffset"][0]), int(now.timestamp() * 1000))


if __name__ == "__main__":
    unittest.main()
