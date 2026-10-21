from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.nic_owner_reported_rewards import load_owner_reported_rewards, valid_owner_report


class OwnerReportedRewardTests(unittest.TestCase):
    def event(self, **overrides):
        row = {
            "event_id": "owner-report-1",
            "post_id": "374795126927596",
            "reward_amount_usdc": 0.201,
            "currency": "USDC",
            "reported_at": "2026-10-20T16:00:00+00:00",
            "report_source": "ACCOUNT_OWNER_REPORTED",
            "verification_status": "OWNER_REPORTED",
        }
        row.update(overrides)
        return row

    def test_accepts_exact_post_and_timezone_aware_owner_report(self):
        self.assertTrue(valid_owner_report(self.event()))
        self.assertTrue(valid_owner_report(self.event(post_id="https://www.binance.com/en/square/post/374795126927596")))

    def test_rejects_naive_timestamp_invalid_amount_or_wrong_status(self):
        self.assertFalse(valid_owner_report(self.event(reported_at="2026-10-20T16:00:00")))
        self.assertFalse(valid_owner_report(self.event(reward_amount_usdc=-1)))
        self.assertFalse(valid_owner_report(self.event(verification_status="PAID_VERIFIED")))

    def test_deduplicates_event_ids_and_sums_distinct_events_per_post(self):
        rows = [
            self.event(),
            self.event(),
            self.event(event_id="owner-report-2", reward_amount_usdc=0.3),
            self.event(event_id="bad", post_id="unknown"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "owner-rewards.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            result = load_owner_reported_rewards(path)
        self.assertEqual(result["374795126927596"]["event_count"], 2)
        self.assertAlmostEqual(result["374795126927596"]["amount_usdc"], 0.501)

    def test_preserves_content_metadata_for_owner_reported_reward_learning(self):
        row = self.event(content_metadata={
            "content_lane": "long_term_thesis",
            "content_format": "text_plus_image",
            "hook_type": "long_term_conviction_with_target",
            "summary": "QNT long-term thesis with entry and target",
            "owner_reported_views": 5100,
            "public_post_url": "https://www.binance.com/en/square/post/374795126927596",
            "creator_origin": "owner_manual",
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "owner-rewards.jsonl"
            path.write_text(json.dumps(row) + chr(10), encoding="utf-8")
            result = load_owner_reported_rewards(path)
        meta = result["374795126927596"]["content_metadata"]
        self.assertEqual(meta["content_lane"], "long_term_thesis")
        self.assertEqual(meta["content_format"], "text_plus_image")
        self.assertEqual(meta["owner_reported_views"], 5100)


if __name__ == "__main__":
    unittest.main()
