"""Fail-closed tool broker joining every NIC read-tool call to owner control.

The broker receives a store object from the trusted API process. Worker/model
arguments never supply owner identity or access to the control database.
"""
from __future__ import annotations

from typing import Any, Callable

from src.nic_tool_registry import ToolExecutionError, execute_tool


class OwnerScopedToolBroker:
    def __init__(self, owner_store: Any, *, grant_id: str, task_id: str,
                 executor: Callable[[str, dict[str, Any] | None], dict[str, Any]] = execute_tool):
        if owner_store is None:
            raise ValueError("owner_control_store_required")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise ValueError("owner_grant_id_required")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id_required")
        self.owner_store = owner_store
        self.grant_id = grant_id
        self.task_id = task_id
        self.executor = executor

    def __call__(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip():
            raise ToolExecutionError("tool_name_invalid")
        resource = f"nic_tool:{name}"
        decision = self.owner_store.authorize_action(
            resource=resource,
            action="execute",
            task_id=self.task_id,
            grant_id=self.grant_id,
        )
        if not isinstance(decision, dict) or decision.get("allowed") is not True:
            reason = decision.get("reason", "owner_authorization_denied") if isinstance(decision, dict) else "owner_authorization_unavailable"
            raise ToolExecutionError(f"owner_authorization_denied:{reason}")
        return self.executor(name, arguments)
