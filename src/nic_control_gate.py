"""Default-deny approval gate for NIC external/plugin actions.

Every external action requires a one-time approval bound to the exact action and
payload. Set NIC_EMERGENCY_STOP=1 for an out-of-band hard stop. This module is a
policy primitive; action executors must call authorize_execution immediately
before acting for the gate to protect them.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DEFAULT_STATE = Path(os.getenv("NIC_CONTROL_STATE_PATH", "data/control/nic_control_state.json"))
_LOCK = threading.RLock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(capability: str, action: str, details: dict[str, Any]) -> str:
    raw = _canonical({"capability": capability, "action": action, "details": details})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ControlGate:
    """Persistent kill switch, approval queue, and append-only audit events."""

    def __init__(self, state_path: str | Path | None = None, approval_ttl_seconds: int = 300):
        self.path = Path(state_path) if state_path else _DEFAULT_STATE
        self.ttl = max(30, min(int(approval_ttl_seconds), 3600))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            if not self.path.exists():
                self._write({"emergency_stop": False, "requests": {}, "audit": []})

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Fail closed: corrupt/missing state must never permit actions.
            return {"emergency_stop": True, "requests": {}, "audit": [{"event": "state_unreadable"}]}
        if not isinstance(data, dict):
            return {"emergency_stop": True, "requests": {}, "audit": [{"event": "state_invalid"}]}
        data.setdefault("emergency_stop", False)
        data.setdefault("requests", {})
        data.setdefault("audit", [])
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=self.path.name, dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def is_stopped(self) -> bool:
        if os.getenv("NIC_EMERGENCY_STOP", "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
        with _LOCK:
            state = self._read()
            if not self.path.exists():
                return True
            return bool(state.get("emergency_stop", True))

    def _event(self, state: dict[str, Any], event: str, **fields: Any) -> None:
        state.setdefault("audit", []).append({"at": _iso(_now()), "event": event, **fields})
        state["audit"] = state["audit"][-1000:]

    def set_emergency_stop(self, enabled: bool, actor: str = "owner") -> dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        with _LOCK:
            state = self._read()
            state["emergency_stop"] = enabled
            if enabled:
                for request in state.get("requests", {}).values():
                    if request.get("status") in {"pending", "approved"}:
                        request["status"] = "cancelled_by_emergency_stop"
            self._event(state, "emergency_stop_enabled" if enabled else "emergency_stop_disabled", actor=actor)
            self._write(state)
            return {"emergency_stop": enabled}

    def request_action(
        self, capability: str, action: str, details: dict[str, Any], requester: str = "nic"
    ) -> dict[str, Any]:
        if not capability.strip() or not action.strip() or not isinstance(details, dict):
            raise ValueError("capability, action, and details are required")
        with _LOCK:
            state = self._read()
            if os.getenv("NIC_EMERGENCY_STOP", "").strip().lower() in {"1", "true", "yes", "on"} or state.get("emergency_stop", True):
                raise RuntimeError("NIC emergency stop is active; no actions can be requested")
            request_id = secrets.token_urlsafe(18)
            now = _now()
            record = {
                "request_id": request_id,
                "capability": capability,
                "action": action,
                "details": details,
                "fingerprint": _fingerprint(capability, action, details),
                "requester": requester,
                "created_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=self.ttl)),
                "status": "pending",
                "approved_by": None,
                "consumed_at": None,
            }
            state.setdefault("requests", {})[request_id] = record
            self._event(state, "action_requested", request_id=request_id, capability=capability, action=action)
            self._write(state)
            # UI can show this exact action, target, and details before approval.
            return {k: record[k] for k in ("request_id", "capability", "action", "details", "created_at", "expires_at", "status")}

    def approve_action(self, request_id: str, approved_by: str = "owner") -> dict[str, Any]:
        with _LOCK:
            state = self._read()
            if os.getenv("NIC_EMERGENCY_STOP", "").strip().lower() in {"1", "true", "yes", "on"} or state.get("emergency_stop", True):
                raise RuntimeError("NIC emergency stop is active")
            record = state.get("requests", {}).get(request_id)
            if not record or record.get("status") != "pending":
                raise ValueError("approval request is missing or no longer pending")
            if _now() >= _parse(record["expires_at"]):
                record["status"] = "expired"
                self._event(state, "approval_expired", request_id=request_id)
                self._write(state)
                raise ValueError("approval request expired")
            record["status"] = "approved"
            record["approved_by"] = approved_by
            record["approved_at"] = _iso(_now())
            self._event(state, "action_approved", request_id=request_id, approved_by=approved_by)
            self._write(state)
            return {"request_id": request_id, "status": "approved", "approved_by": approved_by, "expires_at": record["expires_at"]}

    def deny_action(self, request_id: str, actor: str = "owner") -> dict[str, Any]:
        with _LOCK:
            state = self._read()
            record = state.get("requests", {}).get(request_id)
            if not record or record.get("status") != "pending":
                raise ValueError("request is missing or no longer pending")
            record["status"] = "denied"
            self._event(state, "action_denied", request_id=request_id, actor=actor)
            self._write(state)
            return {"request_id": request_id, "status": "denied"}

    def authorize_execution(self, request_id: str, capability: str, action: str, details: dict[str, Any]) -> bool:
        """Consume the matching approval once; call immediately before tool execution."""
        with _LOCK:
            state = self._read()
            env_stop = os.getenv("NIC_EMERGENCY_STOP", "").strip().lower() in {"1", "true", "yes", "on"}
            if env_stop or state.get("emergency_stop", True):
                self._event(state, "execution_blocked_emergency_stop", request_id=request_id)
                self._write(state)
                return False
            record = state.get("requests", {}).get(request_id)
            if not record or record.get("status") != "approved":
                self._event(state, "execution_blocked_no_approval", request_id=request_id)
                self._write(state)
                return False
            if _now() >= _parse(record["expires_at"]):
                record["status"] = "expired"
                self._event(state, "execution_blocked_expired", request_id=request_id)
                self._write(state)
                return False
            exact = _fingerprint(capability, action, details)
            if not secrets.compare_digest(record.get("fingerprint", ""), exact):
                self._event(state, "execution_blocked_payload_mismatch", request_id=request_id)
                self._write(state)
                return False
            record["status"] = "consumed"
            record["consumed_at"] = _iso(_now())
            self._event(state, "action_authorized_once", request_id=request_id, capability=capability, action=action)
            self._write(state)
            return True

    def list_requests(self, statuses: set[str] | None = None) -> list[dict[str, Any]]:
        """Return safe request summaries for the owner console."""
        with _LOCK:
            state = self._read()
            requests = list(state.get("requests", {}).values())
            if statuses:
                requests = [r for r in requests if r.get("status") in statuses]
            requests.sort(key=lambda r: r.get("created_at", ""), reverse=True)
            return [
                {k: r.get(k) for k in (
                    "request_id", "capability", "action", "details", "created_at",
                    "expires_at", "status", "approved_by", "consumed_at"
                )}
                for r in requests[-100:]
            ]

    def status(self) -> dict[str, Any]:
        with _LOCK:
            state = self._read()
            return {
                "emergency_stop": self.is_stopped(),
                "pending_approvals": sum(1 for r in state.get("requests", {}).values() if r.get("status") == "pending"),
                "approved_not_consumed": sum(1 for r in state.get("requests", {}).values() if r.get("status") == "approved"),
                "audit_events": len(state.get("audit", [])),
            }
