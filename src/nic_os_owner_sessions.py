"""Short-lived server-side browser sessions for the NIC owner control plane.
The owner API token is exchanged over HTTPS and never placed in browser storage.
Only a random HttpOnly session cookie and a per-session CSRF token reach the UI.
Sessions are in-memory and intentionally expire on process restart.
"""
from __future__ import annotations
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class OwnerSession:
    csrf_token: str
    expires_at: float

class OwnerSessionStore:
    def __init__(self, *, ttl_seconds: int = 1800, clock=time.time):
        if not isinstance(ttl_seconds, int) or not 60 <= ttl_seconds <= 43200:
            raise ValueError("session_ttl_must_be_60_to_43200_seconds")
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, OwnerSession] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _digest(cookie: str) -> str:
        return hashlib.sha256(cookie.encode("utf-8")).hexdigest()

    def create(self) -> tuple[str, str, int]:
        cookie = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        expires = self._clock() + self.ttl_seconds
        with self._lock:
            self._sessions[self._digest(cookie)] = OwnerSession(csrf, expires)
        return cookie, csrf, self.ttl_seconds

    def authorize(self, cookie: str | None, csrf: str | None) -> bool:
        if not isinstance(cookie, str) or not cookie or not isinstance(csrf, str) or not csrf:
            return False
        key = self._digest(cookie)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return False
            if self._clock() >= session.expires_at:
                self._sessions.pop(key, None)
                return False
            return secrets.compare_digest(session.csrf_token, csrf)

    def revoke(self, cookie: str | None) -> None:
        if isinstance(cookie, str) and cookie:
            with self._lock:
                self._sessions.pop(self._digest(cookie), None)
