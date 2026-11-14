import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from src.nic_assistant_chat import make_handler
from src.nic_os_owner_control_store import OwnerControlStore


class OwnerSessionApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in (
            "NIC_OWNER_CONTROL_TOKEN", "NIC_OWNER_IDENTITY",
            "NIC_OWNER_SESSION_ALLOW_INSECURE_LOCALHOST", "NIC_CHAT_ALLOWED_ORIGINS",
            "NIC_OWNER_SESSION_TTL_SECONDS", "NIC_OWNER_SESSION_DB", "NIC_TASK_RUNTIME_DB",
        )}
        os.environ["NIC_OWNER_CONTROL_TOKEN"] = "test-owner-token"
        os.environ["NIC_OWNER_IDENTITY"] = "owner-1"
        os.environ["NIC_OWNER_SESSION_ALLOW_INSECURE_LOCALHOST"] = "1"
        os.environ["NIC_OWNER_SESSION_TTL_SECONDS"] = "1800"
        os.environ["NIC_OWNER_SESSION_DB"] = os.path.join(self.tmp.name, "browser-sessions.sqlite3")
        os.environ["NIC_TASK_RUNTIME_DB"] = os.path.join(self.tmp.name, "tasks.sqlite3")
        self.store = OwnerControlStore(os.path.join(self.tmp.name, "owner.db"), owner_identity="owner-1")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(owner_store=self.store))
        host, port = self.server.server_address
        self.host, self.port = host, port
        self.origin = f"http://{host}:{port}"
        os.environ["NIC_CHAT_ALLOWED_ORIGINS"] = self.origin
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def call(self, method, path, payload=None, cookie=None, csrf=None, origin=True):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=3)
        headers = {}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = self.origin
        if cookie:
            headers["Cookie"] = cookie
        if csrf:
            headers["X-NIC-CSRF"] = csrf
        body = json.dumps(payload) if payload is not None else None
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read() or b"{}")
        result_headers = dict(response.getheaders())
        conn.close()
        return response.status, data, result_headers

    def test_browser_session_controls_stop_grant_and_revoke(self):
        status, data, headers = self.call("POST", "/control/session/login", {"owner_token": "test-owner-token"})
        self.assertEqual(status, 200)
        self.assertTrue(data["authenticated"])
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = data["csrf_token"]

        status, _, _ = self.call("GET", "/control/autonomy/status", cookie=cookie, csrf=csrf, origin=False)
        self.assertEqual(status, 200)

        status, data, _ = self.call("POST", "/control/autonomy/resume", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertFalse(data["emergency_stop"])

        status, data, _ = self.call("POST", "/control/autonomy/grants", {
            "mode": "full_power", "task_ids": ["task-1"],
            "scopes": [{"resource": "nic_tool:search_public_news", "actions": ["execute"]}],
            "duration_seconds": 900,
        }, cookie, csrf)
        self.assertEqual(status, 201)
        grant_id = data["grant"]["grant_id"]

        status, data, _ = self.call("GET", "/control/autonomy/status", cookie=cookie, csrf=csrf, origin=False)
        self.assertEqual(status, 200)
        self.assertEqual(data["recent_grants"][0]["grant_id"], grant_id)
        self.assertEqual(data["recent_grants"][0]["mode"], "full_power")

        status, data, _ = self.call("POST", f"/control/autonomy/grants/{grant_id}/revoke", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertTrue(data["revoked"])

        status, _, _ = self.call("POST", "/control/autonomy/stop", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertTrue(self.store.status()["emergency_stop"])

        status, _, _ = self.call("POST", "/control/session/logout", {}, cookie, csrf)
        self.assertEqual(status, 200)
        status, _, _ = self.call("GET", "/control/autonomy/status", cookie=cookie, csrf=csrf, origin=False)
        self.assertEqual(status, 401)

    def test_browser_session_survives_api_handler_restart(self):
        status, data, headers = self.call("POST", "/control/session/login", {"owner_token": "test-owner-token"})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = data["csrf_token"]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(owner_store=self.store))
        self.host, self.port = self.server.server_address
        self.origin = f"http://{self.host}:{self.port}"
        os.environ["NIC_CHAT_ALLOWED_ORIGINS"] = self.origin
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        status, _, _ = self.call("GET", "/control/autonomy/status", cookie=cookie, csrf=csrf, origin=False)
        self.assertEqual(status, 200)


    def test_owner_task_api_create_list_events_and_controls(self):
        status, _, _ = self.call("GET", "/control/tasks", origin=False)
        self.assertEqual(status, 401)

        status, data, headers = self.call(
            "POST", "/control/session/login", {"owner_token": "test-owner-token"}
        )
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = data["csrf_token"]

        status, data, _ = self.call(
            "POST", "/control/tasks",
            {"goal": "Research creators and summarize evidence", "priority": 4},
            cookie, csrf,
        )
        self.assertEqual(status, 201)
        task_id = data["task"]["task_id"]
        self.assertEqual(data["task"]["status"], "queued")

        status, data, _ = self.call("GET", "/control/tasks", cookie=cookie, csrf=csrf, origin=False)
        self.assertEqual(status, 200)
        self.assertEqual(data["tasks"][0]["task_id"], task_id)

        status, data, _ = self.call(
            "GET", f"/control/tasks/{task_id}", cookie=cookie, csrf=csrf, origin=False
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["task"]["goal"], "Research creators and summarize evidence")

        status, data, _ = self.call(
            "GET", f"/control/tasks/{task_id}/events", cookie=cookie, csrf=csrf, origin=False
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["events"][0]["event_type"], "task.created")

        status, data, _ = self.call("POST", f"/control/tasks/{task_id}/pause", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "task_paused")

        status, data, _ = self.call("POST", f"/control/tasks/{task_id}/resume", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "task_resumed")

        status, data, _ = self.call("POST", f"/control/tasks/{task_id}/cancel", {}, cookie, csrf)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "task_cancelled")
        self.assertEqual(data["task"]["status"], "cancelled")

    def test_task_api_does_not_disclose_another_owner_task(self):
        from src.nic_os_task_runtime import TaskRuntimeStore
        task_store = TaskRuntimeStore(os.environ["NIC_TASK_RUNTIME_DB"])
        private = task_store.create_task(owner_id="different-owner", goal="private")
        # Login cookie is required in addition to the CSRF token.
        status, data, headers = self.call(
            "POST", "/control/session/login", {"owner_token": "test-owner-token"}
        )
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = data["csrf_token"]
        status, data, _ = self.call(
            "GET", f"/control/tasks/{private['task_id']}", cookie=cookie, csrf=csrf, origin=False
        )
        self.assertEqual(status, 404)
        self.assertEqual(data["error"], "task_not_found")


    def test_direct_operator_tool_execution_requires_task_bound_grant(self):
        status, data, headers = self.call(
            "POST", "/control/session/login", {"owner_token": "test-owner-token"}
        )
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = data["csrf_token"]
        status, data, _ = self.call(
            "POST", "/operator/execute",
            {"tool": "get_live_market_data", "arguments": {}},
            cookie, csrf,
        )
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "operator_execution_requires_exact_task_bound_grant")

    def test_login_rejects_wrong_origin_and_wrong_owner_token(self):
        status, _, _ = self.call("POST", "/control/session/login", {"owner_token": "bad"}, origin=False)
        self.assertEqual(status, 403)
        status, _, _ = self.call("POST", "/control/session/login", {"owner_token": "bad"})
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
