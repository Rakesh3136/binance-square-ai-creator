"""Persistent, bounded NIC task queue and append-only task event history.

This module is a storage primitive only. It does not execute task payloads,
schedule work, authenticate callers, or grant tool permissions. Keep its
database private to the trusted runtime service, never worker containers.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import secrets
import sqlite3
import uuid
from typing import Any


STATUSES = {"queued", "running", "paused", "completed", "failed", "cancelled"}
MAX_TASK_GOAL = 8000
MAX_RETRIES = 3


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timestamps_must_be_timezone_aware")
    return current.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat()


class TaskRuntimeStore:
    """SQLite-backed task state with atomic claims, leases and immutable events."""

    def __init__(self, database: str | Path, *, clock=_now):
        self.database = str(database)
        self.clock = clock
        path = Path(self.database)
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS nic_tasks (
                    task_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                        ('queued','running','paused','completed','failed','cancelled')),
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    lease_id TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    result_json TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS nic_tasks_queue
                    ON nic_tasks(status, priority DESC, created_at ASC);
                CREATE TABLE IF NOT EXISTS nic_task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES nic_tasks(task_id),
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS nic_task_events_task
                    ON nic_task_events(task_id, event_id);
                CREATE TRIGGER IF NOT EXISTS nic_task_events_no_update
                    BEFORE UPDATE ON nic_task_events
                    BEGIN SELECT RAISE(ABORT, 'task_events_are_append_only'); END;
                CREATE TRIGGER IF NOT EXISTS nic_task_events_no_delete
                    BEFORE DELETE ON nic_task_events
                    BEGIN SELECT RAISE(ABORT, 'task_events_are_append_only'); END;
            """)
        try:
            os.chmod(self.database, 0o600)
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _event(db: sqlite3.Connection, task_id: str, at: datetime,
               actor: str, event_type: str, details: dict[str, Any] | None = None) -> None:
        db.execute(
            "INSERT INTO nic_task_events(task_id,occurred_at,actor,event_type,details_json) "
            "VALUES(?,?,?,?,?)",
            (task_id, _stamp(at), actor, event_type,
             json.dumps(details or {}, ensure_ascii=False, sort_keys=True)),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for key in ("result_json",):
            raw = item.pop(key, None)
            item["result"] = json.loads(raw) if raw else None
        return item

    def create_task(self, *, owner_id: str, goal: str, priority: int = 0,
                    max_attempts: int = 3) -> dict[str, Any]:
        if not isinstance(owner_id, str) or not owner_id.strip() or len(owner_id) > 200:
            raise ValueError("owner_id_invalid")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > MAX_TASK_GOAL:
            raise ValueError("task_goal_invalid")
        if isinstance(priority, bool) or not isinstance(priority, int) or not -10 <= priority <= 10:
            raise ValueError("task_priority_invalid")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= MAX_RETRIES:
            raise ValueError("max_attempts_must_be_between_1_and_3")
        now = _now(self.clock())
        task_id = str(uuid.uuid4())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO nic_tasks(task_id,owner_id,goal,status,priority,created_at,updated_at,max_attempts) "
                "VALUES(?,?,?,'queued',?,?,?,?)",
                (task_id, owner_id.strip(), goal.strip(), priority, _stamp(now), _stamp(now), max_attempts),
            )
            self._event(db, task_id, now, owner_id.strip(), "task.created",
                        {"status": "queued", "priority": priority, "max_attempts": max_attempts})
            db.commit()
        return self.get_task(task_id)

    def claim_next(self, *, worker_id: str, lease_seconds: int = 90,
                   eligible_task_ids: list[str] | None = None) -> dict[str, Any] | None:
        if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 200:
            raise ValueError("worker_id_invalid")
        if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 15 <= lease_seconds <= 900:
            raise ValueError("lease_seconds_must_be_between_15_and_900")
        now = _now(self.clock())
        expiry = now + timedelta(seconds=lease_seconds)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            expired = db.execute(
                "SELECT task_id, attempts, max_attempts FROM nic_tasks "
                "WHERE status='running' AND lease_expires_at <= ?", (_stamp(now),)
            ).fetchall()
            for row in expired:
                next_status = "queued" if row["attempts"] < row["max_attempts"] else "failed"
                db.execute(
                    "UPDATE nic_tasks SET status=?, lease_id=NULL, lease_owner=NULL, "
                    "lease_expires_at=NULL, updated_at=?, error=? WHERE task_id=?",
                    (next_status, _stamp(now), "worker_lease_expired", row["task_id"]),
                )
                self._event(db, row["task_id"], now, "runtime", "task.lease_expired",
                            {"next_status": next_status})
            if eligible_task_ids is not None:
                if not isinstance(eligible_task_ids, list) or any(
                    not isinstance(item, str) or not item for item in eligible_task_ids
                ):
                    db.rollback()
                    raise ValueError("eligible_task_ids_invalid")
                if not eligible_task_ids:
                    db.commit()
                    return None
                placeholders = ",".join("?" for _ in eligible_task_ids)
                row = db.execute(
                    "SELECT task_id FROM nic_tasks WHERE status='queued' "
                    f"AND task_id IN ({placeholders}) "
                    "ORDER BY priority DESC, created_at ASC LIMIT 1",
                    tuple(dict.fromkeys(eligible_task_ids)),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT task_id FROM nic_tasks WHERE status='queued' "
                    "ORDER BY priority DESC, created_at ASC LIMIT 1"
                ).fetchone()
            if row is None:
                db.commit()
                return None
            task_id = row["task_id"]
            lease_id = secrets.token_urlsafe(32)
            db.execute(
                "UPDATE nic_tasks SET status='running', attempts=attempts+1, lease_id=?, "
                "lease_owner=?, lease_expires_at=?, updated_at=?, error=NULL WHERE task_id=? AND status='queued'",
                (lease_id, worker_id.strip(), _stamp(expiry), _stamp(now), task_id),
            )
            if db.execute("SELECT changes()").fetchone()[0] != 1:
                db.rollback()
                return None
            self._event(db, task_id, now, worker_id.strip(), "task.claimed",
                        {"lease_expires_at": _stamp(expiry)})
            db.commit()
        task = self.get_task(task_id)
        task["lease_id"] = lease_id
        return task

    def transition(self, task_id: str, *, new_status: str, actor: str,
                   lease_id: str | None = None, result: dict[str, Any] | None = None,
                   error: str | None = None) -> dict[str, Any]:
        if new_status not in STATUSES - {"queued", "running"}:
            raise ValueError("task_transition_target_invalid")
        if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
            raise ValueError("actor_invalid")
        if result is not None and (not isinstance(result, dict) or len(json.dumps(result)) > 20000):
            raise ValueError("task_result_invalid")
        if error is not None and (not isinstance(error, str) or len(error) > 2000):
            raise ValueError("task_error_invalid")
        now = _now(self.clock())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("task_not_found")
            old = row["status"]
            allowed = {
                "queued": {"paused", "cancelled"},
                "running": {"paused", "completed", "failed", "cancelled"},
                "paused": {"cancelled"},
                "failed": set(),
                "completed": set(),
                "cancelled": set(),
            }
            if new_status not in allowed[old]:
                db.rollback()
                raise ValueError(f"task_transition_not_allowed:{old}->{new_status}")
            if old == "running":
                if not lease_id or not secrets.compare_digest(row["lease_id"] or "", lease_id):
                    db.rollback()
                    raise PermissionError("valid_worker_lease_required")
                if row["lease_expires_at"] <= _stamp(now):
                    db.rollback()
                    raise PermissionError("worker_lease_expired")
            if new_status == "completed" and result is None:
                db.rollback()
                raise ValueError("completed_task_requires_result")
            db.execute(
                "UPDATE nic_tasks SET status=?, updated_at=?, lease_id=NULL, lease_owner=NULL, "
                "lease_expires_at=NULL, result_json=?, error=? WHERE task_id=?",
                (new_status, _stamp(now), json.dumps(result, ensure_ascii=False) if result is not None else None,
                 error, task_id),
            )
            self._event(db, task_id, now, actor.strip(), "task." + new_status,
                        {"error": error} if error else {})
            db.commit()
        return self.get_task(task_id)

    def retry_task(self, task_id: str, *, owner_id: str) -> dict[str, Any]:
        now = _now(self.clock())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("task_not_found")
            if row["owner_id"] != owner_id:
                db.rollback()
                raise PermissionError("task_owner_mismatch")
            if row["status"] != "failed" or row["attempts"] >= row["max_attempts"]:
                db.rollback()
                raise ValueError("task_not_retryable")
            db.execute(
                "UPDATE nic_tasks SET status='queued', updated_at=?, error=NULL WHERE task_id=?",
                (_stamp(now), task_id),
            )
            self._event(db, task_id, now, owner_id, "task.requeued", {"attempts": row["attempts"]})
            db.commit()
        return self.get_task(task_id)



    def pause_task(self, task_id: str, *, owner_id: str) -> dict[str, Any]:
        """Owner pause revokes an active worker lease so it cannot commit late output."""
        now = _now(self.clock())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("task_not_found")
            if row["owner_id"] != owner_id:
                db.rollback()
                raise PermissionError("task_owner_mismatch")
            if row["status"] not in {"queued", "running"}:
                db.rollback()
                raise ValueError("task_not_pausable")
            db.execute(
                "UPDATE nic_tasks SET status='paused', updated_at=?, lease_id=NULL, "
                "lease_owner=NULL, lease_expires_at=NULL WHERE task_id=?",
                (_stamp(now), task_id),
            )
            self._event(db, task_id, now, owner_id, "task.paused", {"lease_revoked": True})
            db.commit()
        return self.get_task(task_id)

    def resume_task(self, task_id: str, *, owner_id: str) -> dict[str, Any]:
        """Resume an owner-paused task without resetting its retry budget."""
        now = _now(self.clock())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("task_not_found")
            if row["owner_id"] != owner_id:
                db.rollback()
                raise PermissionError("task_owner_mismatch")
            if row["status"] != "paused":
                db.rollback()
                raise ValueError("task_not_paused")
            db.execute(
                "UPDATE nic_tasks SET status='queued', updated_at=?, error=NULL WHERE task_id=?",
                (_stamp(now), task_id),
            )
            self._event(db, task_id, now, owner_id, "task.resumed", {"status": "queued"})
            db.commit()
        return self.get_task(task_id)

    def cancel_task(self, task_id: str, *, owner_id: str) -> dict[str, Any]:
        """Owner cancellation revokes any active worker lease immediately."""
        now = _now(self.clock())
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                db.rollback()
                raise KeyError("task_not_found")
            if row["owner_id"] != owner_id:
                db.rollback()
                raise PermissionError("task_owner_mismatch")
            if row["status"] not in {"queued", "running", "paused"}:
                db.rollback()
                raise ValueError("task_not_cancellable")
            db.execute(
                "UPDATE nic_tasks SET status='cancelled', updated_at=?, lease_id=NULL, "
                "lease_owner=NULL, lease_expires_at=NULL, error='cancelled_by_owner' WHERE task_id=?",
                (_stamp(now), task_id),
            )
            self._event(db, task_id, now, owner_id, "task.cancelled", {"lease_revoked": True})
            db.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str, *, owner_id: str | None = None) -> dict[str, Any]:
        with closing(self._connect()) as db:
            if owner_id is None:
                row = db.execute("SELECT * FROM nic_tasks WHERE task_id=?", (task_id,)).fetchone()
            else:
                row = db.execute("SELECT * FROM nic_tasks WHERE task_id=? AND owner_id=?", (task_id, owner_id)).fetchone()
        if row is None:
            raise KeyError("task_not_found")
        return self._decode(row)

    def list_tasks(self, *, owner_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("task_limit_must_be_between_1_and_100")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM nic_tasks WHERE owner_id=? ORDER BY created_at DESC LIMIT ?",
                (owner_id, limit),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def list_events(self, task_id: str, *, owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("event_limit_must_be_between_1_and_500")
        with closing(self._connect()) as db:
            exists = db.execute(
                "SELECT 1 FROM nic_tasks WHERE task_id=? AND owner_id=?", (task_id, owner_id)
            ).fetchone()
            if exists is None:
                raise KeyError("task_not_found")
            rows = db.execute(
                "SELECT event_id,task_id,occurred_at,actor,event_type,details_json "
                "FROM nic_task_events WHERE task_id=? ORDER BY event_id DESC LIMIT ?",
                (task_id, limit),
            ).fetchall()
        return [{**dict(row), "details": json.loads(row["details_json"])} for row in reversed(rows)]
