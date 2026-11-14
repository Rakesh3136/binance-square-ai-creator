import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from src.nic_os_task_runtime import TaskRuntimeStore


class TaskRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tasks.sqlite3")
        self.now = [datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)]
        self.store = TaskRuntimeStore(self.path, clock=lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_task_and_events_survive_store_restart(self):
        task = self.store.create_task(owner_id="owner", goal="Research Binance Square creator trends")
        restarted = TaskRuntimeStore(self.path, clock=lambda: self.now[0])
        self.assertEqual(restarted.get_task(task["task_id"])["status"], "queued")
        events = restarted.list_events(task["task_id"], owner_id="owner")
        self.assertEqual([e["event_type"] for e in events], ["task.created"])

    def test_atomic_claim_and_completion_requires_lease(self):
        task = self.store.create_task(owner_id="owner", goal="Prepare research")
        claim = self.store.claim_next(worker_id="worker-a")
        self.assertEqual(claim["task_id"], task["task_id"])
        with self.assertRaises(PermissionError):
            self.store.transition(task["task_id"], new_status="completed", actor="worker-a",
                                  result={"summary": "done"})
        done = self.store.transition(task["task_id"], new_status="completed", actor="worker-a",
                                     lease_id=claim["lease_id"], result={"summary": "done"})
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["result"], {"summary": "done"})

    def test_priority_order(self):
        low = self.store.create_task(owner_id="owner", goal="low", priority=0)
        high = self.store.create_task(owner_id="owner", goal="high", priority=5)
        claim = self.store.claim_next(worker_id="worker")
        self.assertEqual(claim["task_id"], high["task_id"])
        self.assertNotEqual(claim["task_id"], low["task_id"])

    def test_expired_lease_requeues_with_bounded_attempts(self):
        task = self.store.create_task(owner_id="owner", goal="bounded retry", max_attempts=2)
        first = self.store.claim_next(worker_id="worker", lease_seconds=15)
        self.now[0] += timedelta(seconds=16)
        second = self.store.claim_next(worker_id="worker", lease_seconds=15)
        self.assertEqual(second["task_id"], task["task_id"])
        self.assertEqual(second["attempts"], 2)
        self.now[0] += timedelta(seconds=16)
        self.assertIsNone(self.store.claim_next(worker_id="worker"))
        failed = self.store.get_task(task["task_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "worker_lease_expired")

    def test_retry_requires_owner_and_remaining_attempt_budget(self):
        task = self.store.create_task(owner_id="owner", goal="retry me", max_attempts=2)
        claim = self.store.claim_next(worker_id="worker")
        self.store.transition(task["task_id"], new_status="failed", actor="worker",
                              lease_id=claim["lease_id"], error="temporary")
        with self.assertRaises(PermissionError):
            self.store.retry_task(task["task_id"], owner_id="other")
        self.assertEqual(self.store.retry_task(task["task_id"], owner_id="owner")["status"], "queued")
        claim2 = self.store.claim_next(worker_id="worker")
        self.store.transition(task["task_id"], new_status="failed", actor="worker",
                              lease_id=claim2["lease_id"], error="again")
        with self.assertRaises(ValueError):
            self.store.retry_task(task["task_id"], owner_id="owner")

    def test_owner_isolation_for_lists_and_events(self):
        task = self.store.create_task(owner_id="owner-a", goal="private task")
        self.assertEqual(self.store.list_tasks(owner_id="owner-b"), [])
        with self.assertRaises(KeyError):
            self.store.list_events(task["task_id"], owner_id="owner-b")

    def test_invalid_inputs_and_transitions_fail_closed(self):
        with self.assertRaises(ValueError):
            self.store.create_task(owner_id="owner", goal=" ")
        with self.assertRaises(ValueError):
            self.store.create_task(owner_id="owner", goal="x", max_attempts=9)
        task = self.store.create_task(owner_id="owner", goal="test")
        with self.assertRaises(ValueError):
            self.store.transition(task["task_id"], new_status="completed", actor="owner")

    def test_events_are_append_only(self):
        task = self.store.create_task(owner_id="owner", goal="audit")
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE nic_task_events SET actor='tampered' WHERE task_id=?",
                           (task["task_id"],))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM nic_task_events WHERE task_id=?", (task["task_id"],))


    def test_owner_can_resume_paused_task(self):
        task = self.store.create_task(owner_id="owner", goal="pause and resume")
        self.store.transition(task["task_id"], new_status="paused", actor="owner")
        with self.assertRaises(PermissionError):
            self.store.resume_task(task["task_id"], owner_id="intruder")
        resumed = self.store.resume_task(task["task_id"], owner_id="owner")
        self.assertEqual(resumed["status"], "queued")
        self.assertEqual(resumed["attempts"], 0)

    def test_owner_cancel_revokes_running_worker_lease(self):
        task = self.store.create_task(owner_id="owner", goal="cancel running task")
        claim = self.store.claim_next(worker_id="worker")
        cancelled = self.store.cancel_task(task["task_id"], owner_id="owner")
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(ValueError):
            self.store.transition(task["task_id"], new_status="completed", actor="worker",
                                  lease_id=claim["lease_id"], result={"late": True})

    def test_database_permissions_are_restricted(self):
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_stale_lease_cannot_complete_task(self):
        task = self.store.create_task(owner_id="owner", goal="lease fencing")
        claim = self.store.claim_next(worker_id="worker", lease_seconds=15)
        self.now[0] += timedelta(seconds=16)
        self.store.claim_next(worker_id="worker2", lease_seconds=15)
        with self.assertRaises(PermissionError):
            self.store.transition(task["task_id"], new_status="completed", actor="worker",
                                  lease_id=claim["lease_id"], result={"ok": True})


if __name__ == "__main__":
    unittest.main()
