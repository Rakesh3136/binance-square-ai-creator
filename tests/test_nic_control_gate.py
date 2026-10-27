import json
import os

import pytest

from src.nic_control_gate import ControlGate


def gate(tmp_path, monkeypatch):
    monkeypatch.delenv("NIC_EMERGENCY_STOP", raising=False)
    return ControlGate(tmp_path / "control.json", approval_ttl_seconds=60)


def test_external_action_requires_explicit_approval(tmp_path, monkeypatch):
    g = gate(tmp_path, monkeypatch)
    details = {"post_id": "draft-7", "destination": "Binance Square"}
    request = g.request_action("binance_square", "publish_post", details)
    assert request["status"] == "pending"
    assert not g.authorize_execution(request["request_id"], "binance_square", "publish_post", details)
    assert g.approve_action(request["request_id"])["status"] == "approved"
    assert g.authorize_execution(request["request_id"], "binance_square", "publish_post", details)


def test_approval_is_one_time(tmp_path, monkeypatch):
    g = gate(tmp_path, monkeypatch)
    details = {"file": "report.json"}
    req = g.request_action("files", "write_file", details)
    g.approve_action(req["request_id"])
    assert g.authorize_execution(req["request_id"], "files", "write_file", details)
    assert not g.authorize_execution(req["request_id"], "files", "write_file", details)


def test_approval_is_bound_to_exact_payload(tmp_path, monkeypatch):
    g = gate(tmp_path, monkeypatch)
    req = g.request_action("binance_square", "publish_post", {"text": "Draft A"})
    g.approve_action(req["request_id"])
    assert not g.authorize_execution(req["request_id"], "binance_square", "publish_post", {"text": "Draft B"})


def test_emergency_stop_cancels_pending_and_blocks_execution(tmp_path, monkeypatch):
    g = gate(tmp_path, monkeypatch)
    req = g.request_action("binance_square", "publish_post", {"text": "Draft A"})
    g.set_emergency_stop(True)
    assert g.is_stopped()
    assert not g.authorize_execution(req["request_id"], "binance_square", "publish_post", {"text": "Draft A"})
    with pytest.raises(RuntimeError, match="emergency stop"):
        g.request_action("browser", "click", {"target": "publish"})


def test_environment_stop_is_out_of_band(tmp_path, monkeypatch):
    g = gate(tmp_path, monkeypatch)
    req = g.request_action("browser", "click", {"target": "publish"})
    g.approve_action(req["request_id"])
    monkeypatch.setenv("NIC_EMERGENCY_STOP", "1")
    assert g.is_stopped()
    assert not g.authorize_execution(req["request_id"], "browser", "click", {"target": "publish"})


def test_corrupt_state_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("NIC_EMERGENCY_STOP", raising=False)
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")
    g = ControlGate(path)
    assert g.is_stopped()
