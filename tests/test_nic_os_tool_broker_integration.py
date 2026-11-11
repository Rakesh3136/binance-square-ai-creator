from datetime import datetime, timezone

from src.nic_os_owner_control_store import OwnerControlStore
from src.nic_os_tool_broker import OwnerAuthorizedToolBroker
from src.nic_tool_registry import ToolExecutionError


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def test_real_owner_store_gates_tool_call_and_revocation(tmp_path):
    store = OwnerControlStore(tmp_path / "owner.sqlite3", owner_identity="owner:primary")
    store.set_emergency_stop(authenticated_owner="owner:primary", active=False)
    grant = store.issue_grant(
        authenticated_owner="owner:primary",
        task_ids=["task-1"],
        scopes=[{"resource": "nic_tool:get_live_market_data", "actions": ["execute"]}],
        duration_seconds=3600,
        now=NOW,
    )
    calls = []
    broker = OwnerAuthorizedToolBroker(
        store, grant_id=grant["grant_id"], task_id="task-1",
        executor=lambda name, args: calls.append(name) or {"executed": True},
    )
    assert broker.execute("get_live_market_data", {}) == {"executed": True}
    try:
        broker.execute("search_public_news", {})
        assert False, "unlisted tool must be denied"
    except ToolExecutionError as exc:
        assert "resource_action_out_of_scope" in str(exc)
    assert calls == ["get_live_market_data"]

    store.revoke_grant(authenticated_owner="owner:primary", grant_id=grant["grant_id"])
    try:
        broker.execute("get_live_market_data", {})
        assert False, "revoked grant must be denied"
    except ToolExecutionError as exc:
        assert "owner_grant_revoked" in str(exc)
    assert calls == ["get_live_market_data"]
