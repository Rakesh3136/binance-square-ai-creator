import unittest
from unittest.mock import patch

from src.nic_tool_registry import ToolExecutionError, execute_tool, tool_catalog


class NICToolRegistryTests(unittest.TestCase):
    def test_catalog_is_small_and_read_only(self):
        names = {item["name"] for item in tool_catalog()}
        self.assertEqual(names, {
            "get_agent_registry", "get_creator_dashboard", "list_recent_research"
        })
        self.assertNotIn("publish_post", names)
        self.assertNotIn("run_shell", names)

    def test_unknown_tools_are_rejected(self):
        with self.assertRaisesRegex(ToolExecutionError, "tool_not_allowed"):
            execute_tool("publish_post", {})

    def test_arguments_are_strictly_rejected(self):
        with self.assertRaisesRegex(ToolExecutionError, "tool_arguments_not_supported"):
            execute_tool("get_agent_registry", {"path": "../../secrets"})

    def test_registry_response_is_summarized(self):
        sample = {
            "generated_at": "2026-11-03T00:00:00Z",
            "mission": "autonomous_binance_square_creator",
            "agent_count": 9,
            "operational_agent_count": 6,
            "agents": [{
                "agent_id": "research", "name": "Research Agent",
                "state": "workflow_wired", "limitations": ["evidence-bound"]
            }],
            "policy": {"only_publisher_may_publish": True},
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_agent_registry")
        self.assertEqual(result["agent_count"], 9)
        self.assertEqual(result["agents"][0]["state"], "workflow_wired")
        self.assertTrue(result["policy"]["only_publisher_may_publish"])

    def test_no_file_write_or_subprocess_capability_is_exposed(self):
        source_names = {item["name"] for item in tool_catalog()}
        self.assertFalse(source_names.intersection({"write_file", "run_command", "publish_post"}))


if __name__ == "__main__":
    unittest.main()
