import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.nic_reward_evidence import canonical_post_id, is_verified_reward_event
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


if __name__ == "__main__":
    unittest.main()
