import hashlib
import json
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_module(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

auth = load_module("nic_publication_authorization", "src/nic_publication_authorization.py")
audit = load_module("nic_publication_proof_audit", "src/nic_publication_proof_audit.py")
NOW = datetime.now(timezone.utc).isoformat()


class EditorialAuthorizationTests(unittest.TestCase):
    def fixtures(self):
        text = "Research note: $MAGIC has a conditional market structure worth watching; no entry, stop, target, or instruction is provided."
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (
            {"editorial_auto_publication_enabled": True, "editorial_mode": "EDITORIAL_ONLY", "trade_signal_publication_enabled": False, "live_orders_enabled": False, "requires_human_review_for_editorial": False},
            {"eligible": True, "publication_mode": "EDITORIAL", "trade_authorized": False, "generated_at": NOW},
            {"publish": True, "decision": "EDITORIAL_SIGNAL", "generated_at": NOW},
            {"publish": True, "status": "EDITORIAL_ELIGIBLE", "trade_authorized": False, "generated_at": NOW, "draft_sha256": digest},
            text,
            {"status": "PASS", "draft_sha256": digest},
        )

    def run_auth(self, values):
        p, e, r, lane, text, nic21 = values
        return auth.evaluate(p, e, r, lane, text, nic21=nic21)

    def test_explicit_policy_authorizes_only_final_editorial_draft(self):
        result = self.run_auth(self.fixtures())
        self.assertTrue(result["authorized"])
        self.assertFalse(result["trade_signal_publication_authorized"])
        self.assertFalse(result["live_orders_authorized"])
        self.assertFalse(result["human_review_claimed"])

    def test_trade_mode_never_authorized(self):
        values = list(self.fixtures())
        values[1]["publication_mode"] = "TRADE"
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_missing_explicit_trade_denial_blocks(self):
        values = list(self.fixtures())
        values[1]["trade_authorized"] = True
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_stale_routing_blocks(self):
        values = list(self.fixtures())
        values[2]["generated_at"] = "2020-01-01T00:00:00+00:00"
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_actionable_trade_levels_block(self):
        values = list(self.fixtures())
        values[4] = "Entry: 1.2, Stop-loss: 1.0"
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_required_human_review_is_a_hard_publication_stop(self):
        values = list(self.fixtures())
        values[0]["requires_human_review_for_editorial"] = True
        result = self.run_auth(values)
        self.assertFalse(result["authorized"])
        self.assertTrue(any("mandatory human review is outstanding" in reason for reason in result["reasons"]))

    def test_current_repository_policy_authorizes_only_guarded_editorial_autonomy(self):
        policy = json.loads((ROOT / "nic_publication_policy.json").read_text(encoding="utf-8"))
        self.assertTrue(policy["editorial_auto_publication_enabled"])
        self.assertFalse(policy["requires_human_review_for_editorial"])
        self.assertFalse(policy["trade_signal_publication_enabled"])
        self.assertFalse(policy["live_orders_enabled"])
        values = list(self.fixtures())
        values[0] = policy
        result = self.run_auth(values)
        self.assertTrue(result["authorized"])
        self.assertFalse(result["trade_signal_publication_authorized"])
        self.assertFalse(result["live_orders_authorized"])
        self.assertFalse(result["human_review_claimed"])

    def test_disabled_policy_blocks(self):
        values = list(self.fixtures())
        values[0]["editorial_auto_publication_enabled"] = False
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_missing_or_mismatched_nic21_gate_blocks(self):
        values = list(self.fixtures())
        values[5]["status"] = "BLOCKED"
        self.assertFalse(self.run_auth(values)["authorized"])
        values = list(self.fixtures())
        values[5]["draft_sha256"] = "wrong"
        self.assertFalse(self.run_auth(values)["authorized"])

    def test_final_draft_hash_must_match_both_gates(self):
        values = list(self.fixtures())
        values[4] += " changed"
        self.assertFalse(self.run_auth(values)["authorized"])


class PublicationProofAuditTests(unittest.TestCase):
    def test_current_run_post_id_and_link_confirm_publication(self):
        result = audit.evaluate({"github_run_id": "123", "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE", "post_id": "abc123", "link": "https://www.binance.com/square/post/abc123"}, "123", "success")
        self.assertEqual(result["status"], "CONFIRMED_PUBLISHED")
        self.assertTrue(result["verified"])

    def test_old_run_result_is_not_proof(self):
        result = audit.evaluate({"github_run_id": "old", "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE", "post_id": "abc123", "link": "https://www.binance.com/square/post/abc123"}, "123", "skipped")
        self.assertEqual(result["status"], "NO_VERIFIED_PUBLICATION")
        self.assertFalse(result["verified"])
        self.assertIsNone(result["post_id"])

    def test_504_is_unconfirmed(self):
        result = audit.evaluate({"github_run_id": "123", "status": "PUBLISHED_SUBMITTED_504"}, "123", "success")
        self.assertEqual(result["status"], "SUBMISSION_UNCONFIRMED")
        self.assertFalse(result["verified"])

    def test_success_without_id_is_not_proof(self):
        result = audit.evaluate({"github_run_id": "123", "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE", "link": "https://www.binance.com/square/post/abc"}, "123", "success")
        self.assertEqual(result["status"], "NO_VERIFIED_PUBLICATION")
        self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
