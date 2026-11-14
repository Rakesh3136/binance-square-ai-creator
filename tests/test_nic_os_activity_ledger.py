import sqlite3
import pytest
from src.nic_os_activity_ledger import ActivityLedger


def make_ledger(tmp_path):
    return ActivityLedger(tmp_path / "nic-events.sqlite3")


def test_append_and_read_event_with_evidence(tmp_path):
    ledger = make_ledger(tmp_path)
    event = ledger.append_event(
        task_id="task-1", actor="nic", event_type="test_run",
        action="pytest", result="success", target="tests/",
        permission_scope={"workspace": "task-1"},
        evidence_refs=["artifact://pytest-report"],
        details={"passed": 8},
        occurred_at="2026-11-09T10:00:00Z",
    )
    loaded = ledger.list_events(task_id="task-1")
    assert len(loaded) == 1
    assert loaded[0]["event_id"] == event["event_id"]
    assert loaded[0]["evidence_refs"] == ["artifact://pytest-report"]
    assert loaded[0]["details"]["passed"] == 8


def test_event_rows_cannot_be_updated_or_deleted(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = ActivityLedger(path)
    event = ledger.append_event(
        task_id="task-1", actor="nic", event_type="task", action="start", result="started"
    )
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE nic_activity_events SET result='success' WHERE event_id=?",
                (event["event_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM nic_activity_events WHERE event_id=?",
                (event["event_id"],),
            )


def test_daily_summary_counts_events_without_claiming_learning(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.append_event(
        task_id="task-1", actor="nic", event_type="research", action="read_source",
        result="completed", occurred_at="2026-11-09T10:00:00Z",
    )
    summary = ledger.daily_summary(day="2026-11-09")
    assert summary["event_count"] == 1
    assert summary["breakdown"][0]["event_type"] == "research"
    assert "evidence" in summary["claims_policy"]


def test_invalid_event_is_rejected(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(ValueError, match="required"):
        ledger.append_event(task_id="", actor="nic", event_type="task", action="start", result="ok")


def test_timezone_is_required_for_supplied_timestamp(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(ValueError, match="timezone"):
        ledger.append_event(
            task_id="task-1", actor="nic", event_type="task", action="start",
            result="ok", occurred_at="2026-11-09T10:00:00",
        )
