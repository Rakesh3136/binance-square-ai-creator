import unittest
from unittest.mock import Mock

from src.nic_os_tool_broker import OwnerScopedToolBroker
from src.nic_tool_registry import ToolExecutionError


class OwnerScopedToolBrokerTests(unittest.TestCase):
    def test_authorizes_exact_tool_resource_and_task_before_execution(self):
        store = Mock()
        store.authorize_action.return_value = {"allowed": True}
        executor = Mock(return_value={"value": 1})
        broker = OwnerScopedToolBroker(store, grant_id="grant-1", task_id="task-1", executor=executor)
        self.assertEqual(broker("get_agent_registry", {}), {"value": 1})
        store.authorize_action.assert_called_once_with(
            resource="nic_tool:get_agent_registry", action="execute",
            task_id="task-1", grant_id="grant-1",
        )
        executor.assert_called_once_with("get_agent_registry", {})

    def test_denied_or_unavailable_authorization_never_executes_tool(self):
        for decision in ({"allowed": False, "reason": "emergency_stop_active"}, None):
            with self.subTest(decision=decision):
                store = Mock()
                store.authorize_action.return_value = decision
                executor = Mock()
                broker = OwnerScopedToolBroker(store, grant_id="grant-1",
                                                task_id="task-1", executor=executor)
                with self.assertRaises(ToolExecutionError):
                    broker("get_agent_registry", {})
                executor.assert_not_called()

    def test_requires_explicit_grant_and_task(self):
        with self.assertRaisesRegex(ValueError, "owner_grant_id_required"):
            OwnerScopedToolBroker(Mock(), grant_id="", task_id="task")
        with self.assertRaisesRegex(ValueError, "task_id_required"):
            OwnerScopedToolBroker(Mock(), grant_id="grant", task_id="")


if __name__ == "__main__":
    unittest.main()
