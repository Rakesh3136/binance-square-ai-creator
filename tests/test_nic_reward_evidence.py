import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.nic_reward_evidence import canonical_post_id, is_verified_reward_event, reward_event_rejection_reasons
from src import nic_revenue_pattern_lab as revenue_lab
from src import revenue_content_director as revenue_director


def valid_event(post_id="374795126927596", amount=0.201):
    return {
        "event_id": "reward-event-001",
        "canonical_post_id": post_id,
        "observed_at": "2026-10-16T10:00:00+00:00",
        "verified_at": "2026-10-16T10:05:00+00:00",
        "reward_amount_usdc": amount,
        "currency": "USDC",
        "verified": True,
        "reward_status": "PAID_VERIFIED",
        "source": "user_provided_reward_export",
        "evidence_refs": [{
            "source_id": "reward-export-row-001",
            "sha256": "a" * 64,
            "observed_at": "2026-10-16T10:05:00+00:00",
        }],
    }


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class RewardEvidenceTests(unittest.TestCase):
    def test_accepts_complete_post_linked_reward_evidence(self):
        event = valid_event()
        self.assertTrue(is_verified_reward_event(event))
        self.assertEqual(canonical_post_id(event), "374795126927596")

    def test_rejects_unattributed_notification(self):
        event = {
            "event_id": "notification-1",
            "observed_at": "2026-09-24",
            "reward_amount_usdc": 0.001,
            "currency": "USDC",
            "verified": True,
            "source": "user_provided_binance_square_reward_notification",
            "detail_status": "VERIFIED_REWARD_UNATTRIBUTED_POST",
        }
        self.assertFalse(is_verified_reward_event(event))
        reasons = reward_event_rejection_reasons(event)
        self.assertIn("reward_status_not_paid_verified", reasons)
        self.assertIn("canonical_post_id_missing_or_invalid", reasons)
        self.assertIn("hashed_timestamped_evidence_ref_missing", reasons)

    def test_rejects_missing_hash_or_timezone(self):
        event = valid_event()
        event["evidence_refs"][0]["sha256"] = "not-a-sha"
        self.assertFalse(is_verified_reward_event(event))
        event = valid_event()
        event["observed_at"] = "2026-10-16"
        self.assertFalse(is_verified_reward_event(event))

    def test_rejects_legacy_attribution_flag_as_revenue_proof(self):
        row = {"revenue_verified": True, "verified_revenue": True, "verified_revenue_amount": 99}
        self.assertIsNone(revenue_director.verified_revenue(row))

    def test_revenue_pattern_lab_ignores_attribution_flag_and_accepts_only_verified_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attr = root / "publication_attribution.jsonl"
            perf = root / "square_performance.jsonl"
            rewards = root / "wte_reward_events.jsonl"
            live, intel = root / "live", root / "intelligence"
            out, report = live / "nic_revenue_pattern_lab.json", intel / "nic_revenue_pattern_lab_report.json"
            write_jsonl(attr, [
                {"canonical_post_id": "374795126927596", "category": "research", "format": "analysis", "hook_type": "mechanism", "revenue_verified": True, "revenue_amount": 99},
                {"canonical_post_id": "374947394936090", "category": "research", "format": "analysis", "hook_type": "mechanism", "revenue_verified": True, "revenue_amount": 88},
            ])
            write_jsonl(perf, [])
            legacy = {
                "event_id": "old-notification",
                "canonical_post_id": "374947394936090",
                "observed_at": "2026-09-24",
                "reward_amount_usdc": 0.001,
                "currency": "USDC",
                "verified": True,
                "detail_status": "VERIFIED_REWARD_UNATTRIBUTED_POST",
            }
            write_jsonl(rewards, [legacy, valid_event()])
            with patch.object(revenue_lab, "ATTR", attr), patch.object(revenue_lab, "PERF", perf), patch.object(revenue_lab, "REWARD_EVENTS", rewards), patch.object(revenue_lab, "LIVE", live), patch.object(revenue_lab, "INTEL", intel), patch.object(revenue_lab, "OUT", out), patch.object(revenue_lab, "REPORT", report), patch.object(revenue_lab, "ROOT", root):
                revenue_lab.main()
            result = json.loads((live / "nic_revenue_pattern_lab.json").read_text())
            obs = result["observations"][0]
            self.assertEqual(obs["verified_posts"], 1)
            self.assertAlmostEqual(obs["verified_revenue"], 0.201)
            self.assertEqual(result["accepted_verified_reward_events"], 1)
            self.assertEqual(result["rejected_reward_events"], 1)

    def test_revenue_lab_sums_distinct_rewards_and_ignores_duplicate_event_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attr = root / "publication_attribution.jsonl"
            perf = root / "square_performance.jsonl"
            rewards = root / "wte_reward_events.jsonl"
            live, intel = root / "live", root / "intelligence"
            out, report = live / "nic_revenue_pattern_lab.json", intel / "nic_revenue_pattern_lab_report.json"
            write_jsonl(attr, [
                {"canonical_post_id": "374795126927596", "category": "research", "format": "analysis", "hook_type": "mechanism"}
            ])
            write_jsonl(perf, [])
            first = valid_event(amount=0.201)
            second = valid_event(amount=0.100)
            second["event_id"] = "reward-event-002"
            second["observed_at"] = "2026-10-17T10:00:00+00:00"
            second["verified_at"] = "2026-10-17T10:05:00+00:00"
            duplicate = dict(first)
            write_jsonl(rewards, [first, second, duplicate])
            with patch.object(revenue_lab, "ATTR", attr), patch.object(revenue_lab, "PERF", perf), patch.object(revenue_lab, "REWARD_EVENTS", rewards), patch.object(revenue_lab, "LIVE", live), patch.object(revenue_lab, "INTEL", intel), patch.object(revenue_lab, "OUT", out), patch.object(revenue_lab, "REPORT", report), patch.object(revenue_lab, "ROOT", root):
                revenue_lab.main()
            result = json.loads(out.read_text())
            obs = result["observations"][0]
            self.assertEqual(obs["verified_posts"], 1)
            self.assertAlmostEqual(obs["verified_revenue"], 0.301)
            self.assertEqual(result["accepted_verified_reward_events"], 2)
            self.assertEqual(result["duplicate_reward_event_ids_ignored"], 1)
            self.assertEqual(result["rejected_reward_events"], 0)


    def test_revenue_director_requires_verified_reward_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attr = root / "publication_attribution.jsonl"
            perf = root / "square_performance.jsonl"
            rewards = root / "wte_reward_events.jsonl"
            outcomes = root / "outcomes.jsonl"
            write_jsonl(attr, [{"canonical_post_id": "374795126927596", "revenue_verified": True, "verified_revenue_amount": 99, "content_lane": "research"}])
            write_jsonl(perf, [{"canonical_post_id": "374795126927596", "views": 5100}])
            write_jsonl(outcomes, [])
            with patch.object(revenue_director, "ATTRIBUTION", attr), patch.object(revenue_director, "PERFORMANCE", perf), patch.object(revenue_director, "REWARD_EVENTS", rewards), patch.object(revenue_director, "OUTCOMES", outcomes):
                rewards.write_text("", encoding="utf-8")
                rows = revenue_director.merge_rows()
                self.assertIsNone(revenue_director.verified_revenue(rows[0]))
                write_jsonl(rewards, [valid_event()])
                rows = revenue_director.merge_rows()
                self.assertAlmostEqual(revenue_director.verified_revenue(rows[0]), 0.201)


    def test_revenue_lab_reads_nested_square_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attr, perf, rewards = root / "publication_attribution.jsonl", root / "square_performance.jsonl", root / "wte_reward_events.jsonl"
            live, intel = root / "live", root / "intelligence"
            out, report = live / "nic_revenue_pattern_lab.json", intel / "nic_revenue_pattern_lab_report.json"
            write_jsonl(attr, [{"canonical_post_id": "374795126927596", "category": "research", "portfolio_format": "visual_analysis", "portfolio_hook_type": "curiosity_gap", "visual_attached": True}])
            write_jsonl(perf, [{"canonical_post_id": "374795126927596", "metrics": {"views": 5100, "likes": 51, "comments": 7, "shares": 3}}])
            write_jsonl(rewards, [])
            with patch.object(revenue_lab, "ATTR", attr), patch.object(revenue_lab, "PERF", perf), patch.object(revenue_lab, "REWARD_EVENTS", rewards), patch.object(revenue_lab, "LIVE", live), patch.object(revenue_lab, "INTEL", intel), patch.object(revenue_lab, "OUT", out), patch.object(revenue_lab, "REPORT", report), patch.object(revenue_lab, "ROOT", root):
                revenue_lab.main()
            obs = json.loads(out.read_text())["observations"][0]
            self.assertEqual(obs["views"], 5100)
            self.assertEqual(obs["format"], "visual_analysis")
            self.assertEqual(obs["content_family"], "curiosity_gap")
            self.assertGreater(obs["engagement_per_1000_views"], 0)

    def test_director_reads_nested_metrics_and_preserves_attribution_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attr, perf, rewards, outcomes = (root / n for n in ("attribution.jsonl", "performance.jsonl", "rewards.jsonl", "outcomes.jsonl"))
            write_jsonl(attr, [
                {"canonical_post_id": "374795126927596", "category": "research", "portfolio_format": "visual_analysis", "portfolio_hook_type": "curiosity_gap", "portfolio_visual_type": "chart", "visual_attached": True},
                {"canonical_post_id": "374947394936090", "category": "research", "portfolio_format": "text_analysis", "portfolio_hook_type": "question_led", "visual_attached": False},
            ])
            write_jsonl(perf, [
                {"canonical_post_id": "374795126927596", "category": None, "metrics": {"views": 5100, "likes": 51, "comments": 7, "shares": 3}},
                {"canonical_post_id": "374947394936090", "category": None, "metrics": {"views": 2000, "likes": 20, "comments": 4, "shares": 2}},
            ])
            write_jsonl(rewards, [])
            write_jsonl(outcomes, [])
            with patch.object(revenue_director, "ATTRIBUTION", attr), patch.object(revenue_director, "PERFORMANCE", perf), patch.object(revenue_director, "REWARD_EVENTS", rewards), patch.object(revenue_director, "OUTCOMES", outcomes):
                rows = revenue_director.merge_rows()
            self.assertEqual(rows[0]["category"], "research")
            self.assertEqual(revenue_director.number(rows[0], "views"), 5100)
            score, views = revenue_director.engagement(rows[0])
            self.assertEqual(views, 5100)
            self.assertGreater(score, 0)
            self.assertEqual(revenue_director.group_key(rows[0])[0], "research")
            self.assertEqual(revenue_director.group_key(rows[0])[1], "visual_analysis")
            self.assertEqual(revenue_director.group_key(rows[0])[2], "curiosity_gap")
            self.assertEqual(revenue_director.group_key(rows[0])[3], "chart")
            self.assertEqual(revenue_director.group_key(rows[0])[4], "chart")


if __name__ == "__main__":
    unittest.main()
