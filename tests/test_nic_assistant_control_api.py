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


class NICControlAPITests(unittest.TestCase):
    def setUp(self):
        self._old_chat = os.environ.get("NIC_CHAT_ACCESS_TOKEN")
        self._old_owner = os.environ.get("NIC_OWNER_CONTROL_TOKEN")
        os.environ["NIC_CHAT_ACCESS_TOKEN"] = "chat-test-token"
        os.environ["NIC_OWNER_CONTROL_TOKEN"] = "owner-test-token"
        self.shared_stop_mock = patch("src.nic_assistant_chat.sync_github_emergency_stop")
        self.sync_shared_stop = self.shared_stop_mock.start()
        self.addCleanup(self.shared_stop_mock.stop)
        self.gate = ControlGate(self._temp_path())
        self.gate.set_emergency_stop(False)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.gate))
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

    def request(self, path, token=None, method="GET", payload=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read().decode())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

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


if __name__ == "__main__":
    unittest.main()
