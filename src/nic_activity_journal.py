"""Durable, append-only owner activity journal for NIC.

Stores observable task events and outcomes, never hidden chain-of-thought.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ALLOWED_FIELDS = {
    "task_id", "actor", "action", "status", "summary",
    "evidence_refs", "permission_scope", "error_code",
}
_TEXT_LIMITS = {
    "task_id": 160, "actor": 80, "action": 120, "status": 40,
    "summary": 1200, "permission_scope": 160, "error_code": 120,
}


class ActivityJournal:
    """SQLite-backed append-only log with bounded, structured event fields."""

    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv(
            "NIC_ACTIVITY_JOURNAL_DB",
            "data/control/nic_activity_journal.sqlite3",
        )
        self.path = Path(configured)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    task_id TEXT,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_refs TEXT NOT NULL,
                    permission_scope TEXT,
                    error_code TEXT
                )
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS activity_events_no_update
                BEFORE UPDATE ON activity_events
                BEGIN SELECT RAISE(ABORT, 'activity journal is append-only'); END
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS activity_events_no_delete
                BEFORE DELETE ON activity_events
                BEGIN SELECT RAISE(ABORT, 'activity journal is append-only'); END
            """)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _normalize(event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict) or set(event) - _ALLOWED_FIELDS:
            raise ValueError("activity_event_fields_invalid")
        normalized: dict[str, Any] = {}
        for key, limit in _TEXT_LIMITS.items():
            value = event.get(key)
            if key in {"actor", "action", "status", "summary"} and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"activity_{key}_required")
            if value is not None:
                if not isinstance(value, str) or len(value) > limit:
                    raise ValueError(f"activity_{key}_invalid")
                normalized[key] = value.strip()
            else:
                normalized[key] = None
        refs = event.get("evidence_refs", [])
        if not isinstance(refs, list) or len(refs) > 10 or any(
            not isinstance(ref, str) or not ref.strip() or len(ref) > 500
            for ref in refs
        ):
            raise ValueError("activity_evidence_refs_invalid")
        normalized["evidence_refs"] = refs
        return normalized

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        item = self._normalize(event)
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO activity_events
                (created_at, task_id, actor, action, status, summary,
                 evidence_refs, permission_scope, error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    created_at, item["task_id"], item["actor"], item["action"],
                    item["status"], item["summary"],
                    json.dumps(item["evidence_refs"], ensure_ascii=False),
                    item["permission_scope"], item["error_code"],
                ),
            )
            event_id = cursor.lastrowid
        return {"id": event_id, "created_at": created_at, **item}

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("activity_limit_invalid")
        limit = max(1, min(limit, 200))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM activity_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            item["evidence_refs"] = json.loads(item.pop("evidence_refs"))
            result.append(item)
        return result
