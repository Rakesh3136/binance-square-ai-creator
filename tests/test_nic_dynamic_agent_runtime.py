import unittest
from types import SimpleNamespace

from src.nic_dynamic_agent_runtime import (
    SPECIALIST_PROFILES,
    run_specialist,
    specialist_catalog,
)


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


class DynamicAgentRuntimeTests(unittest.TestCase):
    def test_catalog_is_small_and_task_scoped(self):
        catalog = specialist_catalog()
        self.assertEqual({item["specialty"] for item in catalog}, set(SPECIALIST_PROFILES))
        self.assertLessEqual(len(catalog), 8)
        self.assertTrue(all(item["tools"] for item in catalog))

    def test_worker_executes_only_role_allowlisted_read_tool(self):
        first = SimpleNamespace(
            id="worker-1",
            output_text="",
            output=[SimpleNamespace(
                type="function_call",
                name="get_reward_learning_status",
                arguments="{}",
                call_id="worker-call-1",
            )],
        )
        second = SimpleNamespace(id="worker-2", output_text="Reward evidence is owner-reported.", output=[])
        client = FakeClient([first, second])
        executed = []

        def execute(name, arguments):
            executed.append((name, arguments))
            return {"owner_reported_events": 2, "verified_events": 0}

        result = run_specialist(
            client=client,
            model="test-model",
            specialty="reward_analyst",
            task="Audit the current reward evidence",
            context="Owner supplied reward examples exist.",
            catalog=[
                {"name": "get_reward_learning_status", "description": "read rewards",
                 "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
                {"name": "get_agent_registry", "description": "read registry",
                 "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            ],
            execute_tool=execute,
        )
        self.assertEqual(executed, [("get_reward_learning_status", {})])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["specialty"], "reward_analyst")
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["trading_authority"])
        self.assertIn("owner-reported", result["findings"])
        self.assertEqual(client.responses.calls[0]["tools"][0]["name"], "get_reward_learning_status")

    def test_unknown_specialist_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "specialist_not_allowed"):
            run_specialist(
                client=FakeClient([]), model="test", specialty="shell_operator",
                task="do something", context="", catalog=[], execute_tool=lambda *_: {},
            )

    def test_task_and_context_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "specialist_task_invalid"):
            run_specialist(
                client=FakeClient([]), model="test", specialty="research_analyst",
                task="x" * 4001, context="", catalog=[], execute_tool=lambda *_: {},
            )
        with self.assertRaisesRegex(ValueError, "specialist_context_invalid"):
            run_specialist(
                client=FakeClient([]), model="test", specialty="research_analyst",
                task="research", context="x" * 8001, catalog=[], execute_tool=lambda *_: {},
            )


if __name__ == "__main__":
    unittest.main()
