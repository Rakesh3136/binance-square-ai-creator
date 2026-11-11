from datetime import datetime, timezone, timedelta

import pytest

from nic_os_owner_control_store import OwnerControlStore


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


def store(tmp_path):
    return OwnerControlStore(tmp_path / "owner-plane.sqlite3", owner_identity="owner:primary")


def grant(s):
    s.set_emergency_stop(authenticated_owner="owner:primary", active=False)
    return s.issue_grant(
        authenticated_owner="owner:primary",
        task_ids=["task-1"],
        scopes=[{"resource": "github:repo", "actions": ["read", "create_branch"]}],
        duration_seconds=3600, now=NOW,
    )


def test_bootstrap_fails_closed_and_owner_can_clear_stop(tmp_path):
    s = store(tmp_path)
    assert s.status()["emergency_stop"] is True
    with pytest.raises(PermissionError):
        s.issue_grant(authenticated_owner="owner:primary", task_ids=["t"],
                      scopes=[{"resource": "r", "actions": ["read"]}], now=NOW)
    s.set_emergency_stop(authenticated_owner="owner:primary", active=False)
    assert s.status()["emergency_stop"] is False


def test_grant_authorizes_only_explicit_task_resource_action(tmp_path):
    s = store(tmp_path)
    g = grant(s)
    assert s.authorize_action(resource="github:repo", action="read",
                              task_id="task-1", grant_id=g["grant_id"], now=NOW)["allowed"]
    assert not s.authorize_action(resource="github:other", action="read",
                                  task_id="task-1", grant_id=g["grant_id"], now=NOW)["allowed"]
    assert not s.authorize_action(resource="github:repo", action="push",
                                  task_id="task-1", grant_id=g["grant_id"], now=NOW)["allowed"]
    assert not s.authorize_action(resource="github:repo", action="read",
                                  task_id="task-2", grant_id=g["grant_id"], now=NOW)["allowed"]


def test_revocation_blocks_next_authorization(tmp_path):
    s = store(tmp_path)
    g = grant(s)
    assert s.revoke_grant(authenticated_owner="owner:primary", grant_id=g["grant_id"])
    result = s.authorize_action(resource="github:repo", action="read",
                                task_id="task-1", grant_id=g["grant_id"], now=NOW)
    assert result == {"allowed": False, "reason": "owner_grant_revoked"}


def test_emergency_stop_blocks_even_valid_grant(tmp_path):
    s = store(tmp_path)
    g = grant(s)
    s.set_emergency_stop(authenticated_owner="owner:primary", active=True)
    result = s.authorize_action(resource="github:repo", action="read",
                                task_id="task-1", grant_id=g["grant_id"], now=NOW)
    assert result == {"allowed": False, "reason": "emergency_stop_active"}


def test_non_delegable_actions_stay_blocked_in_full_power(tmp_path):
    s = store(tmp_path)
    g = grant(s)
    result = s.authorize_action(resource="github:repo", action="production_deploy",
                                task_id="task-1", grant_id=g["grant_id"], now=NOW)
    assert not result["allowed"]
    assert result["reason"] == "non_delegable_owner_action"


def test_expiry_blocks_grant(tmp_path):
    s = store(tmp_path)
    g = grant(s)
    result = s.authorize_action(resource="github:repo", action="read",
                                task_id="task-1", grant_id=g["grant_id"],
                                now=NOW + timedelta(hours=1))
    assert not result["allowed"]
    assert result["reason"] == "grant_expired"


def test_owner_identity_mismatch_cannot_mutate_control_plane(tmp_path):
    s = store(tmp_path)
    with pytest.raises(PermissionError):
        s.set_emergency_stop(authenticated_owner="worker:fake", active=False)
    with pytest.raises(PermissionError):
        s.issue_grant(authenticated_owner="worker:fake", task_ids=["t"],
                      scopes=[{"resource": "r", "actions": ["read"]}], now=NOW)


def test_wildcards_and_unbounded_duration_rejected(tmp_path):
    s = store(tmp_path)
    s.set_emergency_stop(authenticated_owner="owner:primary", active=False)
    with pytest.raises(ValueError):
        s.issue_grant(authenticated_owner="owner:primary", task_ids=["t"],
                      scopes=[{"resource": "*", "actions": ["read"]}], now=NOW)
    with pytest.raises(ValueError):
        s.issue_grant(authenticated_owner="owner:primary", task_ids=["t"],
                      scopes=[{"resource": "r", "actions": ["read"]}],
                      duration_seconds=43201, now=NOW)


def test_audit_is_append_only(tmp_path):
    s = store(tmp_path)
    s.set_emergency_stop(authenticated_owner="owner:primary", active=False)
    with s._connect() as db:
        with pytest.raises(Exception):
            db.execute("DELETE FROM owner_control_audit")
