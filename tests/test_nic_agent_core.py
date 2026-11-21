import unittest
from nic_agent_core import plan_task, authorize_action, learning_record, provider_config

class NicAgentCoreTests(unittest.TestCase):
    def test_task_is_planned_not_executed(self):
        task = plan_task("t1", "Research trader pain points", "creator_analyst")
        self.assertEqual(task["status"], "PLANNED_NOT_EXECUTED")
        self.assertFalse(task["role_contract"]["may_publish"])

    def test_unknown_role_fails_closed(self):
        with self.assertRaises(ValueError):
            plan_task("t1", "Do something", "root_admin")

    def test_publish_stays_blocked_even_with_generic_approval(self):
        result = authorize_action("publish_binance_square", {"approved": True, "approved_by": "owner"})
        self.assertFalse(result["allowed"])
        self.assertEqual(result["status"], "EXPLICIT_APPROVAL_AND_SEPARATE_GATE_REQUIRED")

    def test_unknown_side_effect_has_no_executor(self):
        self.assertFalse(authorize_action("send_email")["allowed"])

    def test_learning_record_keeps_claim_unverified(self):
        record = learning_record(source_url="https://example.com/post", captured_at="2026-10-18T00:00:00Z", observation="Post states a breakout occurred", interpretation="Could indicate momentum", confidence=.6)
        self.assertFalse(record["verified_fact"])
        self.assertEqual(record["status"], "NEEDS_EVALUATION")

    def test_provider_config_never_returns_secret_value(self):
        result = provider_config({"NIC_LLM_PROVIDER": "ANTHROPIC_API", "ANTHROPIC_API_KEY": "dummy-secret"})
        self.assertTrue(result["ready"])
        self.assertNotIn("dummy-secret", str(result))

if __name__ == "__main__":
    unittest.main()
