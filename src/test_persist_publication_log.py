import unittest

from persist_publication_log import merge_lines


class PublicationLogPersistenceTests(unittest.TestCase):
    def test_merges_new_rows_without_losing_remote_history(self):
        remote = '{"status":"PUBLISHED","post_id":"1"}\n{"status":"PUBLISHED","post_id":"2"}\n'
        local = '{"status":"PUBLISHED","post_id":"2"}\n{"status":"PUBLISHED","post_id":"3"}\n'
        merged = merge_lines(remote, local)
        self.assertEqual(merged.splitlines(), [
            '{"status":"PUBLISHED","post_id":"1"}',
            '{"status":"PUBLISHED","post_id":"2"}',
            '{"status":"PUBLISHED","post_id":"3"}',
        ])

    def test_merge_is_idempotent(self):
        text = '{"status":"PUBLISH_BLOCKED_DUPLICATE","timestamp":"2026-10-23T00:00:00Z"}\n'
        self.assertEqual(merge_lines(text, text), text)

    def test_ignores_malformed_rows(self):
        merged = merge_lines('not-json\n{"status":"PUBLISHED","post_id":"1"}\n', '')
        self.assertEqual(merged, '{"status":"PUBLISHED","post_id":"1"}\n')


if __name__ == "__main__":
    unittest.main()
