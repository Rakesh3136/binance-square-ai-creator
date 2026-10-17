import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import nic_autonomous_creator_learning as learner


class AutonomousCreatorLearningTests(unittest.TestCase):
    def test_public_engagement_never_claims_earnings_or_enables_posting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples = root / "examples.json"
            examples.write_text(json.dumps([
                {"source_type": "public_square_creator_observation", "post_id": str(123456+i),
                 "creator": "A", "creator_id": "creator-a", "text": f"Original market analysis {i} with useful evidence",
                 "views": 100, "likes": 10, "replies": 2, "shares": 1,
                 "source_url": f"https://www.binance.com/en/square/post/{123456+i}"}
                for i in range(3)
            ]), encoding="utf-8")
            patterns = root / "patterns.json"
            patterns.write_text("{}", encoding="utf-8")
            attribution = root / "attribution.jsonl"
            performance = root / "performance.jsonl"
            rewards = root / "rewards.jsonl"
            attribution.write_text("", encoding="utf-8")
            performance.write_text("", encoding="utf-8")
            rewards.write_text("", encoding="utf-8")
            out, report = root / "out.json", root / "report.json"
            with patch.multiple(learner, EXAMPLES=examples, PATTERNS=patterns, ATTRIBUTION=attribution,
                                PERFORMANCE=performance, REWARD_EVENTS=rewards, OUT=out, REPORT=report):
                self.assertEqual(learner.main(), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["counts"]["public_posts_observed"], 3)
            self.assertEqual(result["counts"]["public_creators_with_minimum_samples"], 1)
            self.assertEqual(result["public_creator_benchmarks"][0]["earnings_status"], "NOT_PUBLICLY_VERIFIED")
            self.assertFalse(result["guardrails"]["automatic_publication_authorized"])
            self.assertFalse(result["guardrails"]["forecast_profitability_proven"])

    def test_only_exact_post_verified_reward_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples = root / "examples.json"
            examples.write_text("[]", encoding="utf-8")
            patterns = root / "patterns.json"
            patterns.write_text("{}", encoding="utf-8")
            attribution = root / "attribution.jsonl"
            attribution.write_text(json.dumps({"canonical_post_id": "123456", "content_lane": "technical", "format": "chart"}) + "\n", encoding="utf-8")
            performance = root / "performance.jsonl"
            performance.write_text(json.dumps({"canonical_post_id": "123456", "views": 500, "likes": 12}) + "\n", encoding="utf-8")
            rewards = root / "rewards.jsonl"
            rewards.write_text(json.dumps({
                "event_id": "paid-1", "verified": True, "reward_status": "PAID_VERIFIED",
                "canonical_post_id": "123456", "reward_amount_usdc": 0.2, "currency": "USDC",
                "observed_at": "2026-10-17T10:00:00+00:00", "verified_at": "2026-10-17T10:01:00+00:00",
                "evidence_refs": [{"source_id": "official-record-1", "sha256": "a" * 64,
                                   "observed_at": "2026-10-17T10:00:00+00:00"}]
            }) + "\n", encoding="utf-8")
            out, report = root / "out.json", root / "report.json"
            with patch.multiple(learner, EXAMPLES=examples, PATTERNS=patterns, ATTRIBUTION=attribution,
                                PERFORMANCE=performance, REWARD_EVENTS=rewards, OUT=out, REPORT=report):
                self.assertEqual(learner.main(), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["counts"]["verified_exact_post_reward_events"], 1)
            self.assertEqual(result["own_post_patterns"][0]["verified_reward_usdc"], 0.2)
            self.assertEqual(result["own_post_patterns"][0]["evidence"], "EXACT_POST_REWARD_PLUS_PERFORMANCE")

    def test_legacy_notification_cannot_become_verified_reward(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "EXAMPLES": root / "examples.json", "PATTERNS": root / "patterns.json",
                "ATTRIBUTION": root / "attribution.jsonl", "PERFORMANCE": root / "performance.jsonl",
                "REWARD_EVENTS": root / "rewards.jsonl", "OUT": root / "out.json", "REPORT": root / "report.json",
            }
            paths["EXAMPLES"].write_text("[]", encoding="utf-8")
            paths["PATTERNS"].write_text("{}", encoding="utf-8")
            paths["ATTRIBUTION"].write_text("", encoding="utf-8")
            paths["PERFORMANCE"].write_text("", encoding="utf-8")
            paths["REWARD_EVENTS"].write_text(json.dumps({"verified": True, "reward_amount_usdc": 0.2, "currency": "USDC"}) + "\n", encoding="utf-8")
            with patch.multiple(learner, **paths):
                self.assertEqual(learner.main(), 0)
            result = json.loads(paths["OUT"].read_text(encoding="utf-8"))
            self.assertEqual(result["counts"]["verified_exact_post_reward_events"], 0)
            self.assertEqual(result["counts"]["rejected_reward_events"], 1)


if __name__ == "__main__":
    unittest.main()
