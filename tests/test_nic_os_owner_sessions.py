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

if __name__ == "__main__":
    unittest.main()
