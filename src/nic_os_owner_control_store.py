"""Persistent owner-control state and atomic per-action authorization.

This store is a backend primitive, not an authentication system. It MUST be
reachable only through an owner-authenticated control-plane API. Worker processes
must not receive its database credentials or call its mutation methods.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nic_os_autonomy_policy import evaluate_owner_autonomy


def _utc(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat()


class OwnerControlStore:
    """Separate owner-plane SQLite store with serialized authorization checks."""

    def __init__(self, database: str | Path, *, owner_identity: str):
        if not isinstance(owner_identity, str) or not owner_identity.strip():
            raise ValueError("configured owner_identity is required")
        self.database = str(database)
        self.owner_identity = owner_identity
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS autonomy_grants (
                    grant_id TEXT PRIMARY KEY,
                    owner_identity TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    task_ids TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS owner_control_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                    emergency_stop INTEGER NOT NULL CHECK(emergency_stop IN (0,1)),
                    updated_at TEXT NOT NULL
                );
                INSERT OR IGNORE INTO owner_control_state
                    (singleton, emergency_stop, updated_at) VALUES (1, 1, 'bootstrap');
                CREATE TABLE IF NOT EXISTS owner_control_audit (
                    event_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event TEXT NOT NULL,
                    grant_id TEXT,
                    details TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS owner_audit_no_update
                    BEFORE UPDATE ON owner_control_audit
                    BEGIN SELECT RAISE(ABORT, 'owner audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS owner_audit_no_delete
                    BEFORE DELETE ON owner_control_audit
                    BEGIN SELECT RAISE(ABORT, 'owner audit is append-only'); END;
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        return db

    def _audit(self, db: sqlite3.Connection, actor: str, event: str,
               grant_id: str | None = None, details: dict[str, Any] | None = None) -> None:
        db.execute(
            "INSERT INTO owner_control_audit VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), _utc(), actor, event, grant_id,
             json.dumps(details or {}, sort_keys=True, separators=(",", ":"))),
        )

    def _require_owner(self, authenticated_owner: str) -> None:
        # authenticated_owner must be injected by the trusted API auth middleware,
        # never copied from request JSON or supplied by a NIC worker.
        if authenticated_owner != self.owner_identity:
            raise PermissionError("owner authentication required")

    def issue_grant(self, *, authenticated_owner: str, task_ids: list[str],
                    scopes: list[dict[str, Any]], mode: str = "full_power",
                    duration_seconds: int = 3600,
                    now: datetime | None = None) -> dict[str, Any]:
        self._require_owner(authenticated_owner)
        if mode not in {"standard", "full_power"}:
            raise ValueError("unsupported autonomy mode")
        if not isinstance(task_ids, list) or not task_ids or any(
            not isinstance(x, str) or not x.strip() for x in task_ids
        ):
            raise ValueError("explicit non-empty task_ids required")
        if not isinstance(scopes, list) or not scopes:
            raise ValueError("explicit resource/action scopes required")
        for scope in scopes:
            if (not isinstance(scope, dict) or not isinstance(scope.get("resource"), str)
                or not scope["resource"].strip() or not isinstance(scope.get("actions"), list)
                or not scope["actions"] or any(not isinstance(a, str) or not a.strip()
                                                for a in scope["actions"])):
                raise ValueError("each scope needs a resource and explicit actions")
            if "*" in scope["actions"] or scope["resource"] == "*":
                raise ValueError("wildcard scopes are forbidden")
        if not isinstance(duration_seconds, int) or not 1 <= duration_seconds <= 43200:
            raise ValueError("grant duration must be 1..43200 seconds")
        issued = now or datetime.now(timezone.utc)
        if issued.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        issued = issued.astimezone(timezone.utc)
        expires = issued.timestamp() + duration_seconds
        from datetime import timedelta
        grant = {
            "grant_id": str(uuid.uuid4()), "approved": True, "revoked": False,
            "approved_by": self.owner_identity, "mode": mode,
            "issued_at": issued.isoformat(),
            "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
            "task_ids": list(dict.fromkeys(task_ids)), "scopes": scopes,
        }
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute("SELECT emergency_stop FROM owner_control_state WHERE singleton=1").fetchone()
            if state is None or state["emergency_stop"]:
                db.rollback()
                raise PermissionError("emergency stop is active")
            db.execute(
                "INSERT INTO autonomy_grants VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (grant["grant_id"], self.owner_identity, mode, grant["issued_at"],
                 grant["expires_at"], json.dumps(grant["task_ids"]),
                 json.dumps(grant["scopes"], sort_keys=True)),
            )
            self._audit(db, authenticated_owner, "grant_issued", grant["grant_id"],
                        {"mode": mode, "task_ids": grant["task_ids"], "expires_at": grant["expires_at"]})
            db.commit()
        return grant

    def revoke_grant(self, *, authenticated_owner: str, grant_id: str) -> bool:
        self._require_owner(authenticated_owner)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE autonomy_grants SET revoked_at=? WHERE grant_id=? AND revoked_at IS NULL",
                (_utc(), grant_id),
            ).rowcount
            if changed:
                self._audit(db, authenticated_owner, "grant_revoked", grant_id)
            db.commit()
        return changed == 1

    def set_emergency_stop(self, *, authenticated_owner: str, active: bool) -> None:
        self._require_owner(authenticated_owner)
        if not isinstance(active, bool):
            raise ValueError("active must be boolean")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE owner_control_state SET emergency_stop=?, updated_at=? WHERE singleton=1",
                (int(active), _utc()),
            )
            self._audit(db, authenticated_owner,
                        "emergency_stop_activated" if active else "emergency_stop_cleared")
            db.commit()

    def authorize_action(self, *, resource: str, action: str, task_id: str,
                         grant_id: str, now: datetime | None = None) -> dict[str, Any]:
        """Atomically read stop+grant and evaluate immediately before tool execution."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute(
                "SELECT emergency_stop FROM owner_control_state WHERE singleton=1"
            ).fetchone()
            if state is None or state["emergency_stop"]:
                db.commit()
                return {"allowed": False, "reason": "emergency_stop_active"}
            row = db.execute(
                "SELECT * FROM autonomy_grants WHERE grant_id=?", (grant_id,)
            ).fetchone()
            if row is None:
                db.commit()
                return {"allowed": False, "reason": "owner_grant_missing"}
            grant = {
                "grant_id": row["grant_id"], "approved": True,
                "revoked": row["revoked_at"] is not None,
                "approved_by": row["owner_identity"], "mode": row["mode"],
                "issued_at": row["issued_at"], "expires_at": row["expires_at"],
                "task_ids": json.loads(row["task_ids"]),
                "scopes": json.loads(row["scopes"]),
            }
            result = evaluate_owner_autonomy(
                grant=grant, owner_identity=self.owner_identity, resource=resource,
                action=action, task_id=task_id, now=now,
            )
            db.commit()
            return result

    def status(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT emergency_stop, updated_at FROM owner_control_state WHERE singleton=1"
            ).fetchone()
            return {"emergency_stop": True if row is None else bool(row["emergency_stop"]),
                    "updated_at": None if row is None else row["updated_at"]}
