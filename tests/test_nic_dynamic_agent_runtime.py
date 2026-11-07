import unittest
from types import SimpleNamespace

from src.nic_dynamic_agent_runtime import (
    CAPABILITY_TOOLS,
    run_specialist,
    capability_catalog,
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
    def test_capability_catalog_is_a_skill_library_not_a_fixed_agent_roster(self):
        catalog = capability_catalog()
        self.assertEqual({item["capability"] for item in catalog}, set(CAPABILITY_TOOLS))
        self.assertLessEqual(len(catalog), 8)
        self.assertTrue(all(item["tools"] for item in catalog))
        self.assertFalse(any("specialty" in item for item in catalog))

    def test_worker_composes_capabilities_and_executes_only_granted_tools(self):
        first = SimpleNamespace(
            id="worker-1", output_text="",
            output=[SimpleNamespace(
                type="function_call", name="get_reward_learning_status",
                arguments="{}", call_id="worker-call-1",
            )],
        )
        second = SimpleNamespace(
            id="worker-2", output_text="Reward evidence remains separately classified.", output=[]
        )
        client = FakeClient([first, second])
        executed = []

        def execute(name, arguments):
            executed.append((name, arguments))
            return {"owner_reported_events": 2, "verified_events": 0}

        catalog = [
            {"name": "get_reward_learning_status", "description": "read rewards",
             "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "get_agent_registry", "description": "read registry",
             "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "search_public_news", "description": "news",
             "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                            "required": ["query"], "additionalProperties": False}},
        ]
        result = run_specialist(
            client=client, model="test-model", role="Reward and cohort evidence auditor",
            task="Audit the current reward evidence", context="Owner supplied examples exist.",
            capabilities=["reward_analytics", "creator_cohorts"],
            catalog=catalog, execute_tool=execute,
        )
        self.assertEqual(executed, [("get_reward_learning_status", {})])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["role"], "Reward and cohort evidence auditor")
        self.assertEqual(set(result["capabilities"]), {"reward_analytics", "creator_cohorts"})
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["trading_authority"])
        self.assertEqual(
            set(item["name"] for item in client.responses.calls[0]["tools"]),
            {"get_reward_learning_status"},
        )

    def test_retired_300_node_mesh_and_generated_artifact_are_absent(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "src/agent_mesh_300.py").exists())
        self.assertFalse((root / "data/live/agent_mesh_300.json").exists())
        for relative in ("src/creator_agent_supervisor.py", "src/agent_strategy_bridge.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("agent_mesh_300", source)
            self.assertNotIn("300-agent", source)

    def test_invalid_or_privilege_escalating_capabilities_are_rejected(self):
        for capabilities in ([], ["shell"], ["reward_analytics", "reward_analytics"],
                             ["reward_analytics", "market_data", "news_discovery",
                              "research_evidence", "creator_cohorts"]):
            with self.subTest(capabilities=capabilities):
                with self.assertRaisesRegex(ValueError, "specialist_capabilities_invalid"):
                    run_specialist(
                        client=FakeClient([]), model="test", role="Research helper",
                        task="research", context="", capabilities=capabilities,
                        catalog=[], execute_tool=lambda *_: {},
                    )

    def test_unknown_or_invalid_role_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "specialist_role_invalid"):
            run_specialist(
                client=FakeClient([]), model="test", role="shell\noperator",
                task="do something", context="", capabilities=["research_evidence"],
                catalog=[], execute_tool=lambda *_: {},
            )

    def test_task_and_context_are_bounded(self):
        common = dict(
            client=FakeClient([]), model="test", role="Research helper",
            capabilities=["research_evidence"], catalog=[], execute_tool=lambda *_: {},
        )
        with self.assertRaisesRegex(ValueError, "specialist_task_invalid"):
            run_specialist(**common, task="x" * 4001, context="")
        with self.assertRaisesRegex(ValueError, "specialist_context_invalid"):
            run_specialist(**common, task="research", context="x" * 8001)


if __name__ == "__main__":
    unittest.main()
