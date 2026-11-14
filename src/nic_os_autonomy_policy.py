"""Owner-granted NIC autonomy profiles with non-delegable safety boundaries.
Pure evaluator only; production must obtain grants from an independent owner
control plane and consult revocation state on every tool call.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

MAX_GRANT_SECONDS = 12 * 60 * 60
NON_DELEGABLE_ACTIONS = {
    "production_deploy", "financial_transfer", "withdrawal", "trade", "purchase",
    "change_security_policy", "change_emergency_stop", "grant_permissions",
    "revoke_owner_permissions", "read_owner_control_credentials",
    "read_private_keys", "read_recovery_phrases", "bypass_provider_verification",
}

def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)

def evaluate_owner_autonomy(*, grant: dict[str, Any] | None, owner_identity: str,
                            resource: str, action: str, task_id: str,
                            now: datetime | None = None) -> dict[str, Any]:
    """Evaluate one action against a time-limited owner-issued grant."""
    def deny(reason: str) -> dict[str, Any]:
        return {"allowed": False, "reason": reason}
    if action in NON_DELEGABLE_ACTIONS:
        return deny("non_delegable_owner_action")
    if not isinstance(grant, dict):
        return deny("owner_grant_missing")
    if grant.get("approved") is not True:
        return deny("owner_grant_not_approved")
    if grant.get("revoked") is True:
        return deny("owner_grant_revoked")
    if not isinstance(owner_identity, str) or not owner_identity.strip():
        return deny("owner_identity_missing")
    if grant.get("approved_by") != owner_identity:
        return deny("grant_not_from_configured_owner")
    grant_id = grant.get("grant_id")
    if not isinstance(grant_id, str) or not grant_id.strip():
        return deny("grant_id_missing")
    mode = grant.get("mode")
    if mode not in {"standard", "full_power"}:
        return deny("unknown_autonomy_mode")
    issued, expires = _time(grant.get("issued_at")), _time(grant.get("expires_at"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued is None or expires is None or expires <= issued:
        return deny("grant_timestamps_invalid")
    if issued > current:
        return deny("grant_from_future")
    if current >= expires:
        return deny("grant_expired")
    if (expires - issued).total_seconds() > MAX_GRANT_SECONDS:
        return deny("grant_duration_exceeds_limit")
    task_ids = grant.get("task_ids")
    if not isinstance(task_ids, list) or not task_ids or task_id not in task_ids:
        return deny("task_not_granted")
    scopes = grant.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        return deny("scopes_missing")
    matched = any(isinstance(s, dict) and s.get("resource") == resource
                  and isinstance(s.get("actions"), list) and action in s["actions"]
                  for s in scopes)
    if not matched:
        return deny("resource_action_out_of_scope")
    return {"allowed": True, "reason": "owner_granted_scoped_autonomy",
            "mode": mode, "grant_id": grant_id, "task_id": task_id,
            "resource": resource, "action": action, "expires_at": expires.isoformat()}
