"""Durable short-lived browser sessions for NIC's owner control plane.

Only hashes of the random cookie and CSRF token are persisted. The raw
owner bearer token is exchanged once and is never stored in this database.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OwnerSession:
    csrf_digest: str
    expires_at: float


class OwnerSessionStore:
    def __init__(self, *, ttl_seconds: int = 1800, clock=time.time,
                 database: str | Path | None = None):
        if not isinstance(ttl_seconds, int) or not 60 <= ttl_seconds <= 43200:
            raise ValueError("session_ttl_must_be_60_to_43200_seconds")
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self.database = str(database) if database is not None else None
        self._sessions: dict[str, OwnerSession] = {}
        self._lock = threading.RLock()
        if self.database:
            path = Path(self.database)
            path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("""
                    CREATE TABLE IF NOT EXISTS owner_browser_sessions (
                        cookie_digest TEXT PRIMARY KEY,
                        csrf_digest TEXT NOT NULL,
                        expires_at REAL NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                db.execute(
                    "CREATE INDEX IF NOT EXISTS owner_browser_sessions_expiry "
                    "ON owner_browser_sessions(expires_at)"
                )
            try:
                os.chmod(self.database, 0o600)
            except OSError:
                # The deployment must still enforce private-volume permissions.
                pass

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def create(self) -> tuple[str, str, int]:
        cookie = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        now = self._clock()
        expires = now + self.ttl_seconds
        cookie_digest = self._digest(cookie)
        csrf_digest = self._digest(csrf)
        if self.database:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM owner_browser_sessions WHERE expires_at <= ?", (now,))
                db.execute(
                    "INSERT INTO owner_browser_sessions "
                    "(cookie_digest, csrf_digest, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (cookie_digest, csrf_digest, expires, now),
                )
                db.commit()
        else:
            with self._lock:
                self._sessions[cookie_digest] = OwnerSession(csrf_digest, expires)
        return cookie, csrf, self.ttl_seconds

    def authorize(self, cookie: str | None, csrf: str | None) -> bool:
        if not isinstance(cookie, str) or not cookie or not isinstance(csrf, str) or not csrf:
            return False
        cookie_digest = self._digest(cookie)
        csrf_digest = self._digest(csrf)
        now = self._clock()
        if self.database:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT csrf_digest, expires_at FROM owner_browser_sessions "
                    "WHERE cookie_digest = ?", (cookie_digest,)
                ).fetchone()
                if row is None:
                    db.commit()
                    return False
                if now >= row["expires_at"]:
                    db.execute(
                        "DELETE FROM owner_browser_sessions WHERE cookie_digest = ?",
                        (cookie_digest,),
                    )
                    db.commit()
                    return False
                valid = secrets.compare_digest(row["csrf_digest"], csrf_digest)
                db.commit()
                return valid
        with self._lock:
            session = self._sessions.get(cookie_digest)
            if session is None:
                return False
            if now >= session.expires_at:
                self._sessions.pop(cookie_digest, None)
                return False
            return secrets.compare_digest(session.csrf_digest, csrf_digest)

    def revoke(self, cookie: str | None) -> None:
        if not isinstance(cookie, str) or not cookie:
            return
        digest = self._digest(cookie)
        if self.database:
            with self._connect() as db:
                db.execute(
                    "DELETE FROM owner_browser_sessions WHERE cookie_digest = ?",
                    (digest,),
                )
        else:
            with self._lock:
                self._sessions.pop(digest, None)
