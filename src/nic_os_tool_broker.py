"""Fail-closed authorization boundary for NIC model-requested tool calls."""
from __future__ import annotations

import os
from typing import Any, Callable

from src.nic_os_owner_control_store import OwnerControlStore
from src.nic_tool_registry import ToolExecutionError, execute_tool


class OwnerAuthorizedToolBroker:
    """Check a live owner grant immediately before every model tool execution.

    The grant ID is only a selector, not a credential. Authorization comes from
    the owner-control database and is checked for the exact task, tool resource,
    and execute action on every call. A missing store/grant denies execution.
    """

    def __init__(
        self,
        store: OwnerControlStore | None,
        *,
        grant_id: str | None,
        task_id: str | None,
        executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        stop_check: Callable[[], bool] | None = None,
    ):
        self.store = store
        self.grant_id = grant_id
        self.task_id = task_id
        self.executor = executor or execute_tool
        self.stop_check = stop_check

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if os.getenv("NIC_EMERGENCY_STOP", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise ToolExecutionError("emergency_stop_active")
        if self.stop_check is not None and self.stop_check():
            raise ToolExecutionError("emergency_stop_active")
        if self.store is None or not self.grant_id or not self.task_id:
            raise ToolExecutionError("owner_autonomy_grant_required")
        if not isinstance(name, str) or not name.strip():
            raise ToolExecutionError("tool_name_invalid")
        decision = self.store.authorize_action(
            resource=f"nic_tool:{name}",
            action="execute",
            task_id=self.task_id,
            grant_id=self.grant_id,
        )
        if not decision.get("allowed"):
            raise ToolExecutionError(f"owner_autonomy_denied:{decision.get('reason', 'unknown')}")
        return self.executor(name, arguments)
