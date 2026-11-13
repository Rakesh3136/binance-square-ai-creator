import os
import sqlite3
import tempfile
import unittest

from src.nic_os_owner_sessions import OwnerSessionStore


class OwnerSessionTests(unittest.TestCase):
    def test_session_requires_cookie_and_matching_csrf(self):
        store = OwnerSessionStore()
        cookie, csrf, ttl = store.create()
        self.assertGreaterEqual(ttl, 60)
        self.assertTrue(store.authorize(cookie, csrf))
        self.assertFalse(store.authorize(cookie, "wrong"))
        self.assertFalse(store.authorize("wrong", csrf))

    def test_revocation_blocks_next_request(self):
        store = OwnerSessionStore()
        cookie, csrf, _ = store.create()
        store.revoke(cookie)
        self.assertFalse(store.authorize(cookie, csrf))

    def test_expired_session_is_rejected(self):
        now = [1000.0]
        store = OwnerSessionStore(ttl_seconds=60, clock=lambda: now[0])
        cookie, csrf, _ = store.create()
        now[0] += 61
        self.assertFalse(store.authorize(cookie, csrf))

    def test_cookie_is_not_stored_in_plaintext(self):
        store = OwnerSessionStore()
        cookie, _, _ = store.create()
        self.assertNotEqual(store._digest(cookie), cookie)

    def test_ttl_is_bounded(self):
        with self.assertRaises(ValueError):
            OwnerSessionStore(ttl_seconds=1)

    def test_persistent_session_survives_store_recreation_and_revocation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sessions.sqlite3")
            first = OwnerSessionStore(database=path)
            cookie, csrf, _ = first.create()
            second = OwnerSessionStore(database=path)
            self.assertTrue(second.authorize(cookie, csrf))
            second.revoke(cookie)
            self.assertFalse(first.authorize(cookie, csrf))

    def test_persistent_sessions_expire_across_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.0]
            path = os.path.join(directory, "sessions.sqlite3")
            first = OwnerSessionStore(database=path, ttl_seconds=60, clock=lambda: now[0])
            cookie, csrf, _ = first.create()
            now[0] += 61
            second = OwnerSessionStore(database=path, ttl_seconds=60, clock=lambda: now[0])
            self.assertFalse(second.authorize(cookie, csrf))

    def test_database_contains_only_digests_and_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sessions.sqlite3")
            store = OwnerSessionStore(database=path)
            cookie, csrf, _ = store.create()
            with sqlite3.connect(path) as db:
                row = db.execute(
                    "SELECT cookie_digest, csrf_digest FROM owner_browser_sessions"
                ).fetchone()
            self.assertNotIn(cookie, row)
            self.assertNotIn(csrf, row)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
