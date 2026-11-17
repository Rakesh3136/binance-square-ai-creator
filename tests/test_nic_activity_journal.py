import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from src.nic_activity_journal import ActivityJournal
from src.nic_assistant_chat import make_handler


class NICActivityJournalTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="nic-activity-")
        self.db_path = os.path.join(self.tempdir.name, "activity.sqlite3")
        self.journal = ActivityJournal(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def sample_event(self):
        return {
            "task_id": "task-123",
            "actor": "research_specialist",
            "action": "collect_source",
            "status": "completed",
            "summary": "Collected and checked two primary sources.",
            "evidence_refs": ["https://example.com/source"],
            "permission_scope": "web:read",
        }

    def test_append_and_persistence_across_instances(self):
        saved = self.journal.append(self.sample_event())
        self.assertEqual(saved["task_id"], "task-123")
        reopened = ActivityJournal(self.db_path)
        events = reopened.list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], saved["id"])
        self.assertEqual(events[0]["evidence_refs"], ["https://example.com/source"])

    def test_events_are_append_only(self):
        self.journal.append(self.sample_event())
        with sqlite3.connect(self.db_path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM activity_events")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE activity_events SET status='changed'")

    def test_rejects_unknown_fields_and_oversized_values(self):
        event = self.sample_event()
        event["private_chain_of_thought"] = "should never be stored"
        with self.assertRaisesRegex(ValueError, "activity_event_fields_invalid"):
            self.journal.append(event)
        event = self.sample_event()
        event["summary"] = "x" * 1201
        with self.assertRaisesRegex(ValueError, "activity_summary_invalid"):
            self.journal.append(event)

    def test_list_limit_is_bounded(self):
        for index in range(5):
            event = self.sample_event()
            event["task_id"] = f"task-{index}"
            self.journal.append(event)
        self.assertEqual(len(self.journal.list_events(2)), 2)


class NICActivityJournalAPITests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="nic-activity-api-")
        self.old_owner = os.environ.get("NIC_OWNER_CONTROL_TOKEN")
        self.old_db = os.environ.get("NIC_ACTIVITY_JOURNAL_DB")
        os.environ["NIC_OWNER_CONTROL_TOKEN"] = "activity-owner-token"
        os.environ["NIC_ACTIVITY_JOURNAL_DB"] = os.path.join(self.tempdir.name, "api.sqlite3")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.old_owner is None:
            os.environ.pop("NIC_OWNER_CONTROL_TOKEN", None)
        else:
            os.environ["NIC_OWNER_CONTROL_TOKEN"] = self.old_owner
        if self.old_db is None:
            os.environ.pop("NIC_ACTIVITY_JOURNAL_DB", None)
        else:
            os.environ["NIC_ACTIVITY_JOURNAL_DB"] = self.old_db
        self.tempdir.cleanup()

    def request(self, method, token=None, payload=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base + "/activity", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_activity_routes_require_owner_authentication(self):
        status, payload = self.request("GET")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "owner_unauthorized_or_token_unconfigured")

    def test_owner_can_append_and_read_activity_events(self):
        event = {
            "task_id": "creator-cycle-7",
            "actor": "nic_orchestrator",
            "action": "research_complete",
            "status": "completed",
            "summary": "Research evidence was gathered for the draft.",
            "evidence_refs": ["binance-square-post:123"],
        }
        status, created = self.request("POST", "activity-owner-token", event)
        self.assertEqual(status, 201)
        self.assertEqual(created["event"]["task_id"], "creator-cycle-7")
        status, listing = self.request("GET", "activity-owner-token")
        self.assertEqual(status, 200)
        self.assertTrue(listing["append_only"])
        self.assertFalse(listing["chain_of_thought_exposed"])
        self.assertEqual(len(listing["events"]), 1)
        self.assertEqual(listing["events"][0]["action"], "research_complete")

    def test_api_rejects_unstructured_or_private_fields(self):
        event = {
            "actor": "nic",
            "action": "task",
            "status": "completed",
            "summary": "test",
            "hidden_chain_of_thought": "not allowed",
        }
        status, payload = self.request("POST", "activity-owner-token", event)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "activity_event_fields_invalid")


if __name__ == "__main__":
    unittest.main()
