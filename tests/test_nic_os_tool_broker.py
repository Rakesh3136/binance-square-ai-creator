from src.nic_os_tool_broker import OwnerAuthorizedToolBroker
from src.nic_tool_registry import ToolExecutionError


class FakeStore:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def authorize_action(self, **kwargs):
        self.calls.append(kwargs)
        return {"allowed": self.allowed, "reason": "scope_mismatch"}


def test_broker_checks_exact_tool_and_task_before_execution():
    store = FakeStore(True)
    executed = []
    broker = OwnerAuthorizedToolBroker(
        store, grant_id="grant-1", task_id="task-1",
        executor=lambda name, args: executed.append((name, args)) or {"ok": True},
    )
    assert broker.execute("get_live_market_data", {"symbol": "BTCUSDT"}) == {"ok": True}
    assert store.calls == [{
        "resource": "nic_tool:get_live_market_data",
        "action": "execute", "task_id": "task-1", "grant_id": "grant-1",
    }]
    assert executed == [("get_live_market_data", {"symbol": "BTCUSDT"})]


def test_broker_denies_before_executor_when_scope_rejected():
    store = FakeStore(False)
    executed = []
    broker = OwnerAuthorizedToolBroker(
        store, grant_id="grant-1", task_id="task-1",
        executor=lambda *args: executed.append(args) or {},
    )
    try:
        broker.execute("get_live_market_data", {})
        assert False, "must reject"
    except ToolExecutionError as exc:
        assert "owner_autonomy_denied" in str(exc)
    assert executed == []


def test_missing_store_or_grant_fails_closed():
    for broker in (
        OwnerAuthorizedToolBroker(None, grant_id="g", task_id="t"),
        OwnerAuthorizedToolBroker(FakeStore(), grant_id=None, task_id="t"),
        OwnerAuthorizedToolBroker(FakeStore(), grant_id="g", task_id=None),
    ):
        try:
            broker.execute("get_live_market_data", {})
            assert False, "must reject"
        except ToolExecutionError as exc:
            assert str(exc) == "owner_autonomy_grant_required"


def test_each_execution_rechecks_revocation():
    store = FakeStore(True)
    count = []
    broker = OwnerAuthorizedToolBroker(store, grant_id="g", task_id="t",
        executor=lambda *args: count.append(1) or {})
    broker.execute("get_live_market_data", {})
    store.allowed = False
    try:
        broker.execute("get_live_market_data", {})
        assert False, "revoked grant must deny next call"
    except ToolExecutionError:
        pass
    assert len(store.calls) == 2
    assert len(count) == 1
