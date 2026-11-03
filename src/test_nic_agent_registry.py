import unittest

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
            "service_present_tools_not_connected",
        )
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

    def test_registry_preserves_publication_and_evidence_boundaries(self):
        registry = build_registry()
        self.assertEqual(
            registry["publication_authority"],
            "src/binance_square_publisher.py",
        )
        self.assertTrue(
            registry["policy"]["logical_mesh_nodes_are_not_independent_agents"]
        )
        self.assertTrue(registry["policy"]["only_publisher_may_publish"])
        self.assertTrue(registry["policy"]["quality_gates_must_not_be_weakened"])


if __name__ == "__main__":
    unittest.main()
