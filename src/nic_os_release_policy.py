"""Fail-closed policy for NIC production deployment approvals.

This module evaluates an approval; it does not deploy anything. The deployment
executor must call this policy immediately before using production credentials.
Those credentials must never be available to NIC workers.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_production_deployment(
    *,
    commit_sha: str,
    required_checks: dict[str, str],
    approval: dict[str, Any] | None,
    owner_identity: str,
    emergency_stop: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return allow/deny for one exact commit; never performs deployment.

    Approval contract:
      approved=True, approved_by=<owner_identity>,
      commit_sha=<exact 40-char SHA>, approval_id=<non-empty>,
      approved_at=<timezone-aware ISO timestamp>,
      expires_at=<timezone-aware ISO timestamp>.

    Every required check must be present with conclusion 'success'. Missing,
    unknown, failed, cancelled or skipped checks deny production deployment.
    """
    def deny(reason: str) -> dict[str, Any]:
        return {"allowed": False, "reason": reason, "commit_sha": commit_sha}

    if emergency_stop:
        return deny("emergency_stop_active")
    if not isinstance(commit_sha, str) or not _SHA_RE.fullmatch(commit_sha):
        return deny("invalid_commit_sha")
    if not isinstance(owner_identity, str) or not owner_identity.strip():
        return deny("owner_identity_missing")
    if not isinstance(required_checks, dict) or not required_checks:
        return deny("required_checks_missing")
    if any(value != "success" for value in required_checks.values()):
        return deny("required_checks_not_successful")
    if not isinstance(approval, dict):
        return deny("owner_approval_missing")
    if approval.get("approved") is not True:
        return deny("owner_approval_not_granted")
    if approval.get("approved_by") != owner_identity:
        return deny("approval_not_from_configured_owner")
    if approval.get("commit_sha") != commit_sha:
        return deny("approval_commit_mismatch")
    if not isinstance(approval.get("approval_id"), str) or not approval["approval_id"].strip():
        return deny("approval_id_missing")
    approved_at = _parse_time(approval.get("approved_at"))
    expires_at = _parse_time(approval.get("expires_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if approved_at is None or expires_at is None or expires_at <= approved_at:
        return deny("approval_timestamps_invalid")
    if approved_at > current:
        return deny("approval_from_future")
    if current >= expires_at:
        return deny("approval_expired")
    return {
        "allowed": True,
        "reason": "owner_approved_exact_commit_and_checks_passed",
        "commit_sha": commit_sha,
        "approval_id": approval["approval_id"],
        "approved_by": owner_identity,
        "expires_at": expires_at.isoformat(),
    }
