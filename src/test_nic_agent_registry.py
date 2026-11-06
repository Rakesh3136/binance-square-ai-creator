import unittest
from pathlib import Path

from src.nic_agent_registry import build_registry


class NicAgentRegistryTests(unittest.TestCase):
    def test_registry_distinguishes_workflow_agents_from_unimplemented_roles(self):
        registry = build_registry()
        by_id = {agent["agent_id"]: agent for agent in registry["agents"]}

        self.assertEqual(registry["agent_count"], 9)
        self.assertGreaterEqual(registry["operational_agent_count"], 6)
        self.assertEqual(by_id["community_replies"]["state"], "not_implemented")
        self.assertEqual(
            by_id["chat_operator"]["state"],
            "service_present_read_only_tools_connected",
        )
        self.assertIn("nic_tool_registry.py", by_id["chat_operator"]["modules"])
        self.assertIn("bounded_read_only_tool_execution", by_id["chat_operator"]["skills"])
        self.assertEqual(
            by_id["audience_analytics"]["state"],
            "module_present_not_proven_in_canonical_workflow",
        )

    def test_every_claimed_module_exists_and_workflow_wiring_is_real(self):
        registry = build_registry()
        for agent in registry["agents"]:
            self.assertTrue(agent["modules_present"], agent["agent_id"])
            self.assertEqual(agent["missing_modules"], [], agent["agent_id"])
            self.assertEqual(
                agent["workflow_wiring_missing"],
                [],
                agent["agent_id"],
            )


    def test_creator_workflow_refreshes_and_persists_dashboard_snapshot(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/autonomous-market-creator.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("python src/nic_dashboard_state.py"), 2)
        self.assertEqual(workflow.count("data/live/nic_dashboard.json"), 2)

    def test_registry_preserves_publication_and_evidence_boundaries(self):
        registry = build_registry()
        self.assertEqual(
            registry["publication_authority"],
            "src/binance_square_publisher.py",
        )
        self.assertFalse(registry["policy"]["permanent_synthetic_agent_population"])
        self.assertTrue(registry["policy"]["task_scoped_specialists_created_only_when_needed"])
        self.assertTrue(registry["policy"]["specialists_use_role_allowlisted_read_tools"])
        self.assertTrue(registry["policy"]["only_publisher_may_publish"])
        self.assertTrue(registry["policy"]["quality_gates_must_not_be_weakened"])


if __name__ == "__main__":
    unittest.main()
