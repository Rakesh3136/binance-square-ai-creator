import unittest
from types import SimpleNamespace

from src.nic_agent_factory import AgentFactoryError, create_agent, run_specialist_agent
from src.nic_tool_registry import tool_catalog


class FakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


class NICAgentFactoryTests(unittest.TestCase):
    def test_creates_ephemeral_task_scoped_specialist(self):
        agent = create_agent("reward_analyst", "Audit the latest reward evidence")
        self.assertEqual(agent["specialist"], "reward_analyst")
        self.assertEqual(agent["lifecycle"], "ephemeral_task_scoped")
        self.assertIn("get_reward_learning_status", agent["allowed_tools"])
        self.assertNotIn("binance_square_publish", agent["allowed_tools"])

    def test_rejects_unknown_specialist_and_empty_or_oversized_task(self):
        with self.assertRaises(AgentFactoryError):
            create_agent("unrestricted_executor", "Do anything")
        with self.assertRaises(AgentFactoryError):
            create_agent("reward_analyst", " ")
        with self.assertRaises(AgentFactoryError):
            create_agent("reward_analyst", "x" * 2401)

    def test_specialist_executes_only_its_allowlisted_read_tool(self):
        client = FakeClient([
            SimpleNamespace(
                id="specialist-1", output_text="",
                output=[SimpleNamespace(
                    type="function_call", name="get_reward_learning_status",
                    arguments="{}", call_id="tool-1",
                )],
            ),
            SimpleNamespace(id="specialist-2", output_text="Verified and owner-reported records remain separate.", output=[]),
        ])
        executed = []
        def execute(name, args):
            executed.append((name, args))
            return {"verified_count": 0, "owner_reported_count": 2}

        result = run_specialist_agent(
            client, "test-model", "reward_analyst", "Audit reward evidence",
            tool_catalog=tool_catalog(), execute_tool=execute, max_tool_calls=2,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["tool_calls_used"], 1)
        self.assertEqual(executed, [("get_reward_learning_status", {})])
        exposed = {tool["name"] for tool in client.responses.calls[0]["tools"]}
        self.assertIn("get_reward_learning_status", exposed)
        self.assertNotIn("get_creator_dashboard", exposed)
        self.assertNotIn("delegate_to_specialist", exposed)

    def test_specialist_tool_budget_is_bounded(self):
        with self.assertRaises(AgentFactoryError):
            run_specialist_agent(
                FakeClient([]), "test-model", "reward_analyst", "Audit",
                tool_catalog=tool_catalog(), execute_tool=lambda *_: {}, max_tool_calls=3,
            )


if __name__ == "__main__":
    unittest.main()
