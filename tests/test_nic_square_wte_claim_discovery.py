import unittest
from datetime import datetime, timezone

from src.nic_square_wte_claim_discovery import (
    collect_public_claim_posts, extract_post_ids, normalize_public_claim_post,
)

NOW = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
POST_URL = "https://www.binance.com/en/square/post/379000000000001"


class PublicWriteToEarnClaimDiscoveryTests(unittest.TestCase):
    def test_extracts_post_ids_deduplicates_and_handles_escaped_urls(self):
        source = '<a href="/en/square/post/123456">a</a><a href="https://www.binance.com/en/square/post/123456">b</a> \\/en\\/square\\/post\\/654321'
        self.assertEqual(extract_post_ids(source, 10), ["123456", "654321"])

    def test_normalizes_recent_public_claim_and_marks_amount_unverified(self):
        payload = {"code": "000000", "data": {
            "id": "379000000000001", "createTime": int(NOW.timestamp() * 1000) - 2 * 86400 * 1000,
            "bodyTextOnly": "I earned 800 USDC from Write to Earn last week; here is what I learned.",
            "authorName": "Creator Alpha", "authorId": "uid-alpha",
            "viewCount": 8000, "likeCount": 400, "commentCount": 30, "shareCount": 12,
        }}
        post = normalize_public_claim_post(payload, "379000000000001", "writetoearn", NOW)
        self.assertIsNotNone(post)
        self.assertEqual(post["creator"], "Creator Alpha")
        self.assertEqual(post["earnings_status"], "UNVERIFIED_PUBLIC_SELF_REPORT")
        self.assertEqual(post["evidence_type"], "PUBLIC_SELF_REPORTED_WRITE_TO_EARN_CLAIM")
        self.assertEqual(post["source_url"], POST_URL)
        self.assertFalse(post.get("authenticated_session_used", False))

    def test_rejects_undated_old_non_wte_and_non_amount_posts(self):
        base = {
            "id": "379000000000001", "createTime": int(NOW.timestamp() * 1000) - 2 * 86400 * 1000,
            "bodyTextOnly": "I earned 800 USDC from Write to Earn last week; here is what I learned.",
            "authorName": "Creator Alpha",
        }
        self.assertIsNone(normalize_public_claim_post({"data": {**base, "createTime": None}}, "379000000000001", "writetoearn", NOW))
        self.assertIsNone(normalize_public_claim_post({"data": {**base, "createTime": int(NOW.timestamp() * 1000) - 30 * 86400 * 1000}}, "379000000000001", "writetoearn", NOW))
        self.assertIsNone(normalize_public_claim_post({"data": {**base, "bodyTextOnly": "BTC is moving; $BTC has momentum."}}, "379000000000001", "writetoearn", NOW))
        self.assertIsNone(normalize_public_claim_post({"data": {**base, "bodyTextOnly": "Write to Earn needs consistent quality content."}}, "379000000000001", "writetoearn", NOW))

    def test_collects_public_claims_from_hashtag_pages_without_authentication(self):
        source = '<a href="/en/square/post/379000000000001">post</a>'
        payload = {"code": "000000", "data": {
            "id": "379000000000001", "createTime": int(NOW.timestamp() * 1000) - 2 * 86400 * 1000,
            "bodyTextOnly": "I earned 800 USDC from Write to Earn last week; here is what I learned.",
            "authorName": "Creator Alpha", "authorId": "uid-alpha",
            "viewCount": 8000, "likeCount": 400, "commentCount": 30, "shareCount": 12,
        }}
        page_urls = []
        def page_fetch(url):
            page_urls.append(url)
            return source
        def detail_fetch(url, method="GET", payload=None, timeout=15.0):
            return {"code": "000000", "data": {"id": "379000000000001", "createTime": int(NOW.timestamp() * 1000) - 2 * 86400 * 1000,
                "bodyTextOnly": "I earned 800 USDC from Write to Earn last week; here is what I learned.",
                "authorName": "Creator Alpha", "authorId": "uid-alpha", "viewCount": 8000,
                "likeCount": 400, "commentCount": 30, "shareCount": 12}}
        report = collect_public_claim_posts(NOW, page_fetch, detail_fetch, lambda _: None, ("writetoearn",))
        self.assertEqual(report["status"], "PUBLIC_SELF_REPORTED_CLAIMS_FOUND")
        self.assertEqual(report["post_detail_requests"], 1)
        self.assertEqual(report["retained_recent_claim_post_count"], 1)
        self.assertEqual(report["claims"][0]["creator"], "Creator Alpha")
        self.assertFalse(report["evidence_policy"]["public_claims_are_independently_verified"])
        self.assertFalse(report["authenticated_session_used"])
        self.assertEqual(len(page_urls), 1)

    def test_falls_back_to_fresh_public_feed_corpus_when_hashtag_html_has_no_links(self):
        corpus = [{
            "post_id": "379000000000001",
            "source_url": POST_URL,
            "creator": "Creator Alpha",
            "creator_id": "uid-alpha",
            "creator_profile_url": "https://www.binance.com/en/square/profile/CreatorAlpha",
            "posted_at": "2026-10-20T10:00:00+00:00",
            "text": "I earned 800 USDC from Write to Earn last week; here is what I learned.",
            "views": 8000, "likes": 400, "replies": 30, "shares": 12,
            "reply_metric_status": "OBSERVED",
        }]
        report = collect_public_claim_posts(
            NOW, lambda _: "<html><body>client-side page with no post links</body></html>",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not fetch a detail ID")),
            lambda _: None, ("writetoearn",), public_examples=corpus,
        )
        self.assertEqual(report["public_corpus_rows_checked"], 1)
        self.assertEqual(report["public_corpus_claim_matches_before_deduplication"], 1)
        self.assertEqual(report["post_detail_requests"], 0)
        self.assertEqual(report["retained_recent_claim_post_count"], 1)
        self.assertEqual(report["claims"][0]["creator"], "Creator Alpha")
        self.assertEqual(report["claims"][0]["views"], 8000)
        self.assertEqual(report["status"], "PUBLIC_SELF_REPORTED_CLAIMS_FOUND")
        self.assertFalse(report["evidence_policy"]["public_claims_are_independently_verified"])

    def test_page_failures_are_reported_not_fabricated(self):
        def fail(url):
            raise PermissionError("blocked")
        report = collect_public_claim_posts(NOW, fail, lambda *a, **k: {}, lambda _: None, ("writetoearn",))
        self.assertEqual(report["status"], "PUBLIC_HASHTAG_ENDPOINT_BLOCKED")
        self.assertEqual(report["post_detail_requests"], 0)
        self.assertEqual(report["claims"], [])


if __name__ == "__main__":
    unittest.main()
