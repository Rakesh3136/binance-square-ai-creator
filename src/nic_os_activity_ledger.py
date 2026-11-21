"""SQLite-backed NIC OS activity ledger with append-only event semantics.

This local implementation is a development foundation. Production should use a
managed database with separate INSERT-only runtime credentials and owner-controlled
retention/backup. Never store secrets, raw credentials or private chain-of-thought.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REQUIRED = ("task_id", "actor", "event_type", "action", "result")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ActivityLedger:
    """Append-only event store for task, tool, artifact and approval activity."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS nic_activity_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT,
                    permission_scope TEXT NOT NULL,
                    result TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    details TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_nic_events_task_time
                    ON nic_activity_events(task_id, occurred_at);
                CREATE INDEX IF NOT EXISTS idx_nic_events_time
                    ON nic_activity_events(occurred_at);
                CREATE TRIGGER IF NOT EXISTS nic_events_no_update
                    BEFORE UPDATE ON nic_activity_events
                    BEGIN SELECT RAISE(ABORT, 'NIC activity events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS nic_events_no_delete
                    BEFORE DELETE ON nic_activity_events
                    BEGIN SELECT RAISE(ABORT, 'NIC activity events are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def append_event(
        self,
        *,
        task_id: str,
        actor: str,
        event_type: str,
        action: str,
        result: str,
        target: str | None = None,
        permission_scope: dict[str, Any] | None = None,
        evidence_refs: list[str] | None = None,
        details: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        values = {
            "task_id": task_id, "actor": actor, "event_type": event_type,
            "action": action, "result": result,
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("task_id, actor, event_type, action and result are required")
        if target is not None and not isinstance(target, str):
            raise ValueError("target must be a string or None")
        if not isinstance(permission_scope or {}, dict):
            raise ValueError("permission_scope must be an object")
        if not isinstance(evidence_refs or [], list) or any(not isinstance(ref, str) for ref in (evidence_refs or [])):
            raise ValueError("evidence_refs must be a list of strings")
        if not isinstance(details or {}, dict):
            raise ValueError("details must be an object")
        timestamp = occurred_at or _utc_now()
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("occurred_at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        event = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "occurred_at": parsed.astimezone(timezone.utc).isoformat(),
            "actor": actor,
            "event_type": event_type,
            "action": action,
            "target": target,
            "permission_scope": permission_scope or {},
            "result": result,
            "evidence_refs": evidence_refs or [],
            "details": details or {},
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO nic_activity_events
                (event_id, task_id, occurred_at, actor, event_type, action, target,
                 permission_scope, result, evidence_refs, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["event_id"], event["task_id"], event["occurred_at"],
                    event["actor"], event["event_type"], event["action"],
                    event["target"], _json(event["permission_scope"]),
                    event["result"], _json(event["evidence_refs"]), _json(event["details"]),
                ),
            )
        return event

    def list_events(self, *, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        query = "SELECT * FROM nic_activity_events"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY occurred_at DESC, event_id DESC LIMIT ?"
        params += (limit,)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for key in ("permission_scope", "evidence_refs", "details"):
                item[key] = json.loads(item[key])
            output.append(item)
        return output

    def daily_summary(self, *, day: str) -> dict[str, Any]:
        """Summarize event counts for a UTC calendar day; does not infer success."""
        try:
            start = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError("day must be YYYY-MM-DD") from exc
        if start.strftime("%Y-%m-%d") != day:
            raise ValueError("day must be YYYY-MM-DD")
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT event_type, result, COUNT(*) AS count
                FROM nic_activity_events
                WHERE occurred_at >= ? AND occurred_at <= ?
                GROUP BY event_type, result ORDER BY event_type, result""",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) AS count FROM nic_activity_events WHERE occurred_at >= ? AND occurred_at <= ?",
                (start.isoformat(), end.isoformat()),
            ).fetchone()["count"]
        return {
            "day_utc": day,
            "event_count": total,
            "breakdown": [
                {"event_type": row["event_type"], "result": row["result"], "count": row["count"]}
                for row in rows
            ],
            "claims_policy": "counts_only; completion_and_learning_require_linked_evidence",
        }
