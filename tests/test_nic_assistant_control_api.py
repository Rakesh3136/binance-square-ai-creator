import json
import os
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from src.nic_assistant_chat import make_handler
from src.nic_control_gate import ControlGate
from src.nic_os_owner_control_store import OwnerControlStore


class NICControlAPITests(unittest.TestCase):
    def setUp(self):
        self._old_chat = os.environ.get("NIC_CHAT_ACCESS_TOKEN")
        self._old_owner = os.environ.get("NIC_OWNER_CONTROL_TOKEN")
        self._old_origins = os.environ.get("NIC_CHAT_ALLOWED_ORIGINS")
        self._old_owner_identity = os.environ.get("NIC_OS_OWNER_IDENTITY")
        os.environ["NIC_OS_OWNER_IDENTITY"] = "owner-test"
        os.environ["NIC_CHAT_ACCESS_TOKEN"] = "chat-test-token"
        os.environ["NIC_OWNER_CONTROL_TOKEN"] = "owner-test-token"
        os.environ["NIC_CHAT_ALLOWED_ORIGINS"] = "https://example.github.io"
        self.shared_stop_mock = patch("src.nic_assistant_chat.sync_github_emergency_stop")
        self.sync_shared_stop = self.shared_stop_mock.start()
        self.addCleanup(self.shared_stop_mock.stop)
        self.gate = ControlGate(self._temp_path())
        self.gate.set_emergency_stop(False)
        self.owner_store = OwnerControlStore(self._temp_path(), owner_identity="owner-test")
        self.owner_store.set_emergency_stop(authenticated_owner="owner-test", active=False)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.gate, self.owner_store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def _temp_path(self):
        import tempfile
        fd, path = tempfile.mkstemp(prefix="nic-control-test-", suffix=".json")
        os.close(fd)
        os.unlink(path)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self._old_chat is None:
            os.environ.pop("NIC_CHAT_ACCESS_TOKEN", None)
        else:
            os.environ["NIC_CHAT_ACCESS_TOKEN"] = self._old_chat
        if self._old_owner is None:
            os.environ.pop("NIC_OWNER_CONTROL_TOKEN", None)
        else:
            os.environ["NIC_OWNER_CONTROL_TOKEN"] = self._old_owner
        if self._old_origins is None:
            os.environ.pop("NIC_CHAT_ALLOWED_ORIGINS", None)
        else:
            os.environ["NIC_CHAT_ALLOWED_ORIGINS"] = self._old_origins
        if self._old_owner_identity is None:
            os.environ.pop("NIC_OS_OWNER_IDENTITY", None)
        else:
            os.environ["NIC_OS_OWNER_IDENTITY"] = self._old_owner_identity

    def issue_grant(self, resource):
        return self.owner_store.issue_grant(
            authenticated_owner="owner-test", task_ids=["task-1"],
            scopes=[{"resource": resource, "actions": ["execute"]}],
            duration_seconds=3600,
        )

    def request(self, path, token=None, method="GET", payload=None, origin=None):
        headers = {}
        if origin:
            headers["Origin"] = origin
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                self.last_headers = response.headers
                raw = response.read().decode()
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            self.last_headers = exc.headers
            raw = exc.read().decode()
            return exc.code, json.loads(raw) if raw else {}


    def test_dashboard_origin_is_allowed_and_unknown_origin_is_rejected(self):
        status, _ = self.request("/healthz", origin="https://example.github.io")
        self.assertEqual(status, 200)
        self.assertEqual(self.last_headers.get("Access-Control-Allow-Origin"), "https://example.github.io")

        status, _ = self.request("/healthz", origin="https://attacker.example")
        self.assertEqual(status, 200)
        self.assertIsNone(self.last_headers.get("Access-Control-Allow-Origin"))

        status, _ = self.request("/chat", "chat-test-token", method="OPTIONS",
                                 origin="https://example.github.io")
        self.assertEqual(status, 204)
        self.assertIn("Authorization", self.last_headers.get("Access-Control-Allow-Headers", ""))

        status, payload = self.request("/chat", "chat-test-token", method="OPTIONS",
                                       origin="https://attacker.example")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "origin_not_allowed")

    def test_control_routes_require_owner_token(self):
        status, _ = self.request("/control/status")
        self.assertEqual(status, 401)
        status, payload = self.request("/control/status", "owner-test-token")
        self.assertEqual(status, 200)
        self.assertIn("emergency_stop", payload)
        self.assertEqual(payload["external_action_execution"], "not_connected")

    def test_stop_and_resume_are_owner_authenticated(self):
        status, _ = self.request("/control/stop", "wrong", method="POST", payload={})
        self.assertEqual(status, 401)
        status, payload = self.request("/control/stop", "owner-test-token", method="POST", payload={})
        self.assertEqual(status, 200)
        self.assertTrue(payload["emergency_stop"])
        self.sync_shared_stop.assert_called_with(True)
        status, payload = self.request("/control/resume", "owner-test-token", method="POST", payload={})
        self.assertEqual(status, 200)
        self.assertFalse(payload["emergency_stop"])
        self.sync_shared_stop.assert_called_with(False)
        self.assertEqual(payload["shared_stop"], "INACTIVE")

    def test_approval_list_is_owner_authenticated_and_actions_are_one_time(self):
        details = {"post_id": "draft-1", "destination": "Binance Square"}
        request = self.gate.request_action("binance_square", "publish_post", details)
        status, _ = self.request("/control/approvals", "wrong")
        self.assertEqual(status, 401)
        status, payload = self.request("/control/approvals", "owner-test-token")
        self.assertEqual(status, 200)
        self.assertEqual(payload["requests"][0]["request_id"], request["request_id"])
        status, approved = self.request(
            f"/control/approvals/{request['request_id']}/approve",
            "owner-test-token", method="POST", payload={}
        )
        self.assertEqual(status, 200)
        self.assertEqual(approved["status"], "approved")
        self.assertTrue(self.gate.authorize_execution(request["request_id"], "binance_square", "publish_post", details))
        self.assertFalse(self.gate.authorize_execution(request["request_id"], "binance_square", "publish_post", details))

    def test_operator_capabilities_and_execution_require_owner_token(self):
        status, _ = self.request("/operator/capabilities")
        self.assertEqual(status, 401)
        status, payload = self.request("/operator/capabilities", "owner-test-token")
        self.assertEqual(status, 200)
        self.assertEqual(payload["execution_mode"], "owner_authenticated_read_only")
        names = {item["name"] for item in payload["tools"]}
        self.assertIn("get_agent_registry", names)
        self.assertFalse(payload["publishing_available_through_operator"])

        status, _ = self.request(
            "/operator/execute", "wrong", method="POST",
            payload={"tool": "get_agent_registry", "arguments": {}}
        )
        self.assertEqual(status, 401)

    def test_operator_rejects_unapproved_or_mutating_tools(self):
        grant = self.issue_grant("nic_tool:publish_post")
        status, payload = self.request(
            "/operator/execute", "owner-test-token", method="POST",
            payload={"tool": "publish_post", "arguments": {"text": "unsafe"},
                     "autonomy_grant_id": grant["grant_id"], "task_id": "task-1"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "tool_not_allowed")

    def test_operator_rejects_path_injection_arguments(self):
        grant = self.issue_grant("nic_tool:get_agent_registry")
        status, payload = self.request(
            "/operator/execute", "owner-test-token", method="POST",
            payload={"tool": "get_agent_registry", "arguments": {"path": "../../.env"},
                     "autonomy_grant_id": grant["grant_id"], "task_id": "task-1"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "tool_arguments_not_supported")


    def test_owner_can_issue_and_revoke_scoped_autonomy_grants(self):
        status, _ = self.request(
            "/control/autonomy/grants", "wrong", method="POST",
            payload={"task_ids": ["task-1"],
                     "scopes": [{"resource": "nic_tool:get_agent_registry", "actions": ["execute"]}]}
        )
        self.assertEqual(status, 401)
        status, payload = self.request(
            "/control/autonomy/grants", "owner-test-token", method="POST",
            payload={"task_ids": ["task-1"],
                     "scopes": [{"resource": "nic_tool:get_agent_registry", "actions": ["execute"]}],
                     "mode": "full_power", "duration_seconds": 600}
        )
        self.assertEqual(status, 201)
        grant_id = payload["grant"]["grant_id"]
        status, listed = self.request("/control/autonomy/grants", "owner-test-token")
        self.assertEqual(status, 200)
        self.assertEqual(listed["grants"][0]["grant_id"], grant_id)
        status, result = self.request(
            "/operator/execute", "owner-test-token", method="POST",
            payload={"tool": "get_agent_registry", "arguments": {},
                     "autonomy_grant_id": grant_id, "task_id": "task-1"}
        )
        self.assertIn(status, (200, 400))
        status, revoked = self.request(
            f"/control/autonomy/grants/{grant_id}/revoke", "owner-test-token",
            method="POST", payload={}
        )
        self.assertEqual(status, 200)
        self.assertTrue(revoked["revoked"])
        status, denied = self.request(
            "/operator/execute", "owner-test-token", method="POST",
            payload={"tool": "get_agent_registry", "arguments": {},
                     "autonomy_grant_id": grant_id, "task_id": "task-1"}
        )
        self.assertEqual(status, 400)
        self.assertIn("owner_authorization_denied:owner_grant_revoked", denied["error"])

if __name__ == "__main__":
    unittest.main()
