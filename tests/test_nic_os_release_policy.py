from datetime import datetime, timezone
from src.nic_os_release_policy import evaluate_production_deployment

SHA = "a" * 40
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
APPROVAL = {
    "approved": True,
    "approved_by": "owner-1",
    "commit_sha": SHA,
    "approval_id": "approval-123",
    "approved_at": "2026-11-09T11:00:00Z",
    "expires_at": "2026-11-09T13:00:00Z",
}
CHECKS = {"unit": "success", "integration": "success", "security": "success"}


def evaluate(**overrides):
    args = {
        "commit_sha": SHA,
        "required_checks": CHECKS,
        "approval": APPROVAL,
        "owner_identity": "owner-1",
        "emergency_stop": False,
        "now": NOW,
    }
    args.update(overrides)
    return evaluate_production_deployment(**args)


def test_exact_owner_approved_commit_with_successful_checks_is_allowed():
    result = evaluate()
    assert result["allowed"] is True
    assert result["approval_id"] == "approval-123"


def test_missing_owner_approval_is_denied():
    assert evaluate(approval=None)["reason"] == "owner_approval_missing"


def test_approval_for_another_commit_is_denied():
    approval = {**APPROVAL, "commit_sha": "b" * 40}
    assert evaluate(approval=approval)["reason"] == "approval_commit_mismatch"


def test_failed_or_skipped_required_check_is_denied():
    assert evaluate(required_checks={"unit": "success", "security": "skipped"})["reason"] == "required_checks_not_successful"


def test_emergency_stop_overrides_a_valid_approval():
    assert evaluate(emergency_stop=True)["reason"] == "emergency_stop_active"


def test_expired_approval_is_denied():
    approval = {**APPROVAL, "expires_at": "2026-11-09T11:59:59Z"}
    assert evaluate(approval=approval)["reason"] == "approval_expired"


def test_wrong_approver_is_denied():
    approval = {**APPROVAL, "approved_by": "another-user"}
    assert evaluate(approval=approval)["reason"] == "approval_not_from_configured_owner"


def test_missing_required_checks_are_denied():
    assert evaluate(required_checks={})["reason"] == "required_checks_missing"


def test_invalid_sha_is_denied():
    assert evaluate(commit_sha="main")["reason"] == "invalid_commit_sha"
