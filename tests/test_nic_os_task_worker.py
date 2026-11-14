from datetime import datetime, timezone

from src.nic_os_owner_control_store import OwnerControlStore
from src.nic_os_task_runtime import TaskRuntimeStore
from src.nic_os_task_worker import NICTaskWorker


def make_stores(tmp_path):
    tasks = TaskRuntimeStore(tmp_path / "tasks.sqlite3")
    owner = OwnerControlStore(tmp_path / "owner.sqlite3", owner_identity="owner")
    owner.set_emergency_stop(authenticated_owner="owner", active=False)
    return tasks, owner


def issue(owner, task_id):
    return owner.issue_grant(
        authenticated_owner="owner",
        task_ids=[task_id],
        scopes=[{"resource": "nic_tool:get_live_market_data", "actions": ["execute"]}],
        duration_seconds=3600,
    )


def test_worker_runs_only_tasks_with_an_active_exact_task_grant(tmp_path):
    tasks, owner = make_stores(tmp_path)
    blocked = tasks.create_task(owner_id="owner", goal="No grant task", priority=10)
    allowed = tasks.create_task(owner_id="owner", goal="Granted task", priority=0)
    grant = issue(owner, allowed["task_id"])
    seen = []
    worker = NICTaskWorker(
        tasks, owner,
        executor=lambda task, grant_id, store: seen.append((task["task_id"], grant_id)) or "Evidence summary",
    )
    assert worker.run_once()
    assert seen == [(allowed["task_id"], grant["grant_id"])]
    assert tasks.get_task(allowed["task_id"])["status"] == "completed"
    assert tasks.get_task(allowed["task_id"])["result"]["summary"] == "Evidence summary"
    assert tasks.get_task(blocked["task_id"])["status"] == "queued"



def test_worker_never_claims_another_owner_task_even_if_grant_mentions_its_id(tmp_path):
    tasks, owner = make_stores(tmp_path)
    foreign = tasks.create_task(owner_id="different-owner", goal="Foreign task")
    issue(owner, foreign["task_id"])
    called = []
    worker = NICTaskWorker(tasks, owner, executor=lambda *args: called.append(True) or "bad")
    assert worker.run_once() is False
    assert called == []
    assert tasks.get_task(foreign["task_id"])["status"] == "queued"

def test_worker_does_not_claim_when_emergency_stop_is_active(tmp_path):
    tasks, owner = make_stores(tmp_path)
    task = tasks.create_task(owner_id="owner", goal="Stop test")
    issue(owner, task["task_id"])
    owner.set_emergency_stop(authenticated_owner="owner", active=True)
    worker = NICTaskWorker(tasks, owner, executor=lambda *_: "should not run")
    assert worker.run_once() is False
    assert tasks.get_task(task["task_id"])["status"] == "queued"


def test_revoked_grant_during_task_pauses_instead_of_completing(tmp_path):
    tasks, owner = make_stores(tmp_path)
    task = tasks.create_task(owner_id="owner", goal="Revoke during execution")
    grant = issue(owner, task["task_id"])

    def revoke_during_execution(claimed, grant_id, store):
        store.revoke_grant(authenticated_owner="owner", grant_id=grant_id)
        return "This result must not be committed"

    worker = NICTaskWorker(tasks, owner, executor=revoke_during_execution)
    assert worker.run_once()
    current = tasks.get_task(task["task_id"])
    assert current["status"] == "paused"
    assert current["error"] == "owner_stop_or_grant_revoked"


def test_worker_failure_is_bounded_and_recorded_without_exception_details(tmp_path):
    tasks, owner = make_stores(tmp_path)
    task = tasks.create_task(owner_id="owner", goal="Fail safely", max_attempts=2)
    issue(owner, task["task_id"])

    def fail(*_):
        raise RuntimeError("sensitive provider payload must not be persisted")

    worker = NICTaskWorker(tasks, owner, executor=fail)
    assert worker.run_once()
    current = tasks.get_task(task["task_id"])
    assert current["status"] == "failed"
    assert current["attempts"] == 1
    assert "sensitive provider payload" not in current["error"]
