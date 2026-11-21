from datetime import datetime, timezone
import pytest
from src.nic_os_autonomy_policy import evaluate_owner_autonomy

NOW = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
GRANT = {
    "approved": True, "approved_by": "owner-1", "grant_id": "grant-001",
    "mode": "full_power", "issued_at": "2026-11-11T07:00:00Z",
    "expires_at": "2026-11-11T19:00:00Z", "task_ids": ["task-1"],
    "scopes": [
        {"resource": "github:repo-a", "actions": ["read", "write", "create_pr"]},
        {"resource": "browser:binance-square", "actions": ["read", "draft", "publish"]},
        {"resource": "workspace:task-1", "actions": ["read", "write", "execute_tests"]},
    ],
}

def check(**overrides):
    args = {"grant": GRANT, "owner_identity": "owner-1", "resource": "github:repo-a",
            "action": "write", "task_id": "task-1", "now": NOW}
    args.update(overrides)
    return evaluate_owner_autonomy(**args)

def test_full_power_allows_action_inside_owner_scope():
    result = check()
    assert result["allowed"] is True and result["mode"] == "full_power"

def test_full_power_does_not_allow_unlisted_resource_or_action():
    assert check(action="delete")["reason"] == "resource_action_out_of_scope"
    assert check(resource="github:another-repo")["reason"] == "resource_action_out_of_scope"

@pytest.mark.parametrize("action", [
    "production_deploy", "financial_transfer", "withdrawal", "trade", "purchase",
    "change_security_policy", "change_emergency_stop", "grant_permissions",
    "revoke_owner_permissions", "read_owner_control_credentials", "read_private_keys",
    "read_recovery_phrases", "bypass_provider_verification",
])
def test_full_power_never_overrides_non_delegable_actions(action):
    assert check(action=action)["reason"] == "non_delegable_owner_action"

def test_wrong_owner_is_denied():
    assert check(owner_identity="owner-2")["reason"] == "grant_not_from_configured_owner"

def test_revoked_or_unapproved_grant_is_denied():
    assert check(grant={**GRANT, "revoked": True})["reason"] == "owner_grant_revoked"
    assert check(grant={**GRANT, "approved": False})["reason"] == "owner_grant_not_approved"

def test_expired_or_overlong_grant_is_denied():
    expired = {**GRANT, "expires_at": "2026-11-11T07:59:59Z"}
    overlong = {**GRANT, "expires_at": "2026-11-12T08:00:01Z"}
    assert check(grant=expired)["reason"] == "grant_expired"
    assert check(grant=overlong)["reason"] == "grant_duration_exceeds_limit"

def test_task_must_be_explicitly_granted():
    assert check(task_id="other-task")["reason"] == "task_not_granted"

def test_missing_scopes_fail_closed():
    assert check(grant={**GRANT, "scopes": []})["reason"] == "scopes_missing"

def test_timezone_naive_expiry_is_denied():
    invalid = {**GRANT, "expires_at": "2026-11-11T19:00:00"}
    assert check(grant=invalid)["reason"] == "grant_timestamps_invalid"
