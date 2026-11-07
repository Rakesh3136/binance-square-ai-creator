import unittest
from unittest.mock import patch

from src.nic_tool_registry import ToolExecutionError, execute_tool, tool_catalog


class NICToolRegistryTests(unittest.TestCase):
    def test_catalog_exposes_specialist_read_tools_only(self):
        names = {item["name"] for item in tool_catalog()}
        self.assertEqual(names, {
            "get_agent_registry", "get_creator_dashboard", "list_recent_research",
            "get_latest_publication", "get_reward_learning_status",
            "get_creator_period_coverage", "list_creator_study_queue",
            "get_live_market_data", "search_public_news",
            "get_verified_research_evidence", "get_reward_pattern_insights",
        })
        self.assertNotIn("publish_post", names)
        self.assertNotIn("run_shell", names)
        self.assertNotIn("write_file", names)

    def test_unknown_tools_are_rejected(self):
        with self.assertRaisesRegex(ToolExecutionError, "tool_not_allowed"):
            execute_tool("publish_post", {})

    def test_arguments_are_strictly_rejected(self):
        with self.assertRaisesRegex(ToolExecutionError, "tool_arguments_not_supported"):
            execute_tool("get_agent_registry", {"path": "../../secrets"})

    def test_registry_response_is_summarized(self):
        sample = {
            "generated_at": "2026-11-03T00:00:00Z",
            "mission": "autonomous_binance_square_creator",
            "agent_count": 9,
            "operational_agent_count": 6,
            "agents": [{"agent_id": "research", "name": "Research Agent",
                        "state": "workflow_wired", "skills": ["news_research"],
                        "limitations": ["evidence-bound"]}],
            "policy": {"only_publisher_may_publish": True},
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_agent_registry")
        self.assertEqual(result["agent_count"], 9)
        self.assertEqual(result["agents"][0]["state"], "workflow_wired")
        self.assertTrue(result["policy"]["only_publisher_may_publish"])

    def test_latest_publication_requires_exact_verified_id(self):
        rows = [{
            "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
            "post_id": "384495274938003",
            "canonical_post_id": "384495274938003",
            "link": "https://app.binance.com/uni-qr/cpos/384495274938003",
            "publication_id_verified": True,
            "publication_proof": "binance_openapi_response_post_id",
            "symbol": "GPS",
            "monetization": {"revenue_verified": False},
        }]
        with patch("src.nic_tool_registry._read_jsonl_tail", return_value=rows):
            result = execute_tool("get_latest_publication")
        self.assertTrue(result["publication_id_verified"])
        self.assertEqual(result["post_id"], "384495274938003")
        self.assertFalse(result["reward_is_verified"])

    def test_latest_publication_does_not_overstate_unverified_id(self):
        rows = [{"post_id": "123456789", "publication_id_verified": False,
                 "publication_proof": "missing"}]
        with patch("src.nic_tool_registry._read_jsonl_tail", return_value=rows):
            result = execute_tool("get_latest_publication")
        self.assertFalse(result["publication_id_verified"])

    def test_reward_summary_keeps_owner_reported_separate(self):
        sample = {
            "verified_reward_events_7d": 0,
            "verified_usdc_7d": None,
            "owner_reported_usdc_14d": 0.77,
            "owner_reported_events_14d": 1,
            "owner_reported_feedback_status": "OWNER_REPORTED_FEEDBACK_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED",
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_reward_learning_status")
        self.assertEqual(result["summary"]["owner_reported_usdc_14d"], 0.77)
        self.assertIsNone(result["summary"]["verified_usdc_7d"])
        self.assertFalse(result["evidence_policy"]["owner_reported_is_independent_verification"])

    def test_reward_tool_exposes_bounded_exact_post_owner_feedback(self):
        report = {
            "verified_reward_events_7d": 0,
            "verified_usdc_7d": None,
            "owner_reported_usdc_14d": 0.77,
            "owner_reported_events_14d": 1,
        }
        learning = {
            "owner_reported_reward_feedback": {
                "status": "OWNER_REPORTED_FEEDBACK_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED",
                "accepted_report_count": 2,
                "rejected_report_count": 0,
                "7_day": {"reported_event_count": 0, "reported_usdc": None},
                "14_day": {"reported_event_count": 1, "reported_usdc": 0.77},
                "entries": [
                    {
                        "post_id": "376457571598023",
                        "public_post_url": "https://www.binance.com/en/square/post/376457571598023",
                        "reported_reward_usdc": 0.77,
                        "currency": "USDC",
                        "content_lane": "technical_setup",
                        "content_format": "4h_chart_annotated_setup",
                        "verification_status": "OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
                        "evidence_type": "ACCOUNT_OWNER_REPORTED_EXACT_POST_REWARD",
                    },
                    {"post_id": "older-post", "reported_reward_usdc": 0.201},
                ],
            }
        }
        with patch("src.nic_tool_registry._read_json", side_effect=[report, learning]):
            result = execute_tool("get_reward_learning_status")
        feedback = result["owner_reported_reward_feedback"]
        self.assertEqual(feedback["entries_returned"], 2)
        self.assertEqual(feedback["entries"][0]["post_id"], "376457571598023")
        self.assertEqual(feedback["entries"][0]["reported_reward_usdc"], 0.77)
        self.assertEqual(feedback["entries"][0]["content_format"], "4h_chart_annotated_setup")
        self.assertFalse(result["evidence_policy"]["owner_reported_is_independent_verification"])
        self.assertTrue(result["evidence_policy"]["owner_reported_entries_are_post_level_learning_feedback"])
        self.assertIsNone(result["summary"]["verified_usdc_7d"])

    def test_creator_period_tool_never_claims_post_attribution(self):
        sample = {
            "learning_status": "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE",
            "coverage_status": "PARTIAL_OR_BLOCKED_LEADERBOARD_COVERAGE",
            "reward_granularity": "creator_period",
            "coverage": {"leaderboard_creators": 10, "complete_7d": 7},
            "creator_periods": [{
                "creator": "Creator A",
                "profile": {"identity_match": "verified", "collection_status": "complete",
                            "window_7d_complete": True, "window_14d_complete": True,
                            "window_pre_period_14d_complete": True},
                "creator_period_reward": {"amount": 100, "currency": "USDC"},
                "post_cohort_7d": {"post_count": 5},
                "post_cohort_14d": {"post_count": 9},
            }],
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_creator_period_coverage")
        self.assertEqual(result["creators"][0]["posts_7d"], 5)
        self.assertIn("never assigned", result["attribution_policy"])

    def test_creator_queue_labels_public_engagement_not_earnings(self):
        sample = {"creator_study_queue": [{
            "creator": "Creator A", "discovery_window": 14, "posts_observed": 4,
            "public_engagement_rate": 0.05, "earnings_status": "NOT_PUBLICLY_VERIFIED",
            "sample_urls": ["https://example.com/post"],
        }]}
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("list_creator_study_queue")
        self.assertEqual(result["creators"][0]["public_engagement_rate"], 0.05)
        self.assertIn("not evidence of earnings", result["policy"])

    def test_no_file_write_or_subprocess_capability_is_exposed(self):
        names = {item["name"] for item in tool_catalog()}
        self.assertFalse(names.intersection({"write_file", "run_command", "publish_post"}))

    def test_live_market_data_is_allowlisted_and_uses_fixed_binance_host(self):
        import json
        class FakeResponse:
            def __init__(self, payload):
                self.payload = json.dumps(payload).encode("utf-8")
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return self.payload
        ticker = {"symbol": "BTCUSDT", "lastPrice": "90000", "priceChangePercent": "1.5"}
        candles = [[1, "10", "12", "9", "11", "100", 2, "1100"]]
        with patch("src.nic_tool_registry.urllib.request.urlopen", side_effect=[FakeResponse(ticker), FakeResponse(candles)]) as fetch:
            result = execute_tool("get_live_market_data", {"symbol": "BTCUSDT", "interval": "1h"})
        self.assertEqual(result["source"], "Binance public Spot REST API")
        self.assertEqual(result["ticker_24h"]["lastPrice"], "90000")
        self.assertEqual(result["recent_candles"][0]["close"], "11")
        self.assertTrue(all(request.args[0].full_url.startswith("https://api.binance.com/api/v3/") for request in fetch.call_args_list))
        self.assertEqual(result["evidence_class"], "LIVE_PUBLIC_MARKET_OBSERVATION")

    def test_live_market_data_rejects_arbitrary_symbols_and_extra_arguments(self):
        with self.assertRaisesRegex(ToolExecutionError, "market_symbol_or_interval_invalid"):
            execute_tool("get_live_market_data", {"symbol": "BTCUSDT.evil", "interval": "1h"})
        with self.assertRaisesRegex(ToolExecutionError, "market_arguments_invalid"):
            execute_tool("get_live_market_data", {"symbol": "BTCUSDT", "interval": "1h", "url": "https://evil.test"})

    def test_public_news_search_is_discovery_only(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return b"<rss><channel><item><title>Bitcoin ETF update</title><link>https://example.test/story</link><pubDate>Sat, 07 Nov 2026 10:00:00 GMT</pubDate><source>Example</source><description>Primary source update</description></item></channel></rss>"
        with patch("src.nic_tool_registry.urllib.request.urlopen", return_value=FakeResponse()) as fetch:
            result = execute_tool("search_public_news", {"query": "Bitcoin ETF"})
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["title"], "Bitcoin ETF update")
        self.assertIn("DISCOVERY_ONLY", result["results"][0]["evidence_class"])
        self.assertTrue(fetch.call_args.args[0].full_url.startswith("https://news.google.com/rss/search?"))

    def test_reward_pattern_insights_keep_owner_reported_separate(self):
        sample = {
            "generated_at": "2026-11-07T07:12:39Z",
            "status": "COLLECTING_VERIFIED_REWARD_EVIDENCE",
            "accepted_verified_reward_events": 0,
            "rejected_reward_events": 1,
            "observations": [{
                "content_lane": "technical_setup",
                "content_format": "4h_chart_annotated_setup",
                "hook_type": "risk_reward_accumulation_question",
                "posts": 1,
                "verified_posts": 0,
                "verified_revenue": 0,
                "owner_reported_posts": 1,
                "owner_reported_revenue_usdc": 0.77,
                "owner_reported_examples": [{
                    "post_id": "376457571598023",
                    "public_post_url": "https://www.binance.com/en/square/post/376457571598023",
                    "evidence": "OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED"
                }]
            }],
            "next_experiments": [{"test_family": "risk_reward_accumulation_question"}]
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_reward_pattern_insights")
        row = result["observations"][0]
        self.assertEqual(row["owner_reported_reward_usdc"], 0.77)
        self.assertEqual(row["verified_reward_usdc"], 0)
        self.assertEqual(row["owner_reported_examples"][0]["post_id"], "376457571598023")
        self.assertFalse(result["evidence_policy"]["owner_reported_is_independently_verified"])

    def test_verified_research_evidence_preserves_unknown_freshness(self):
        sample = {
            "generated_at": "2026-11-06T07:16:43Z",
            "status": "READY",
            "count": 1,
            "records": [{
                "title": "Headline discovery",
                "url": "https://example.test",
                "source_class": "discovery",
                "retrieval_status": "RETRIEVED",
                "freshness": "UNKNOWN",
                "limitations": ["Primary-source verification required"]
            }]
        }
        with patch("src.nic_tool_registry._read_json", return_value=sample):
            result = execute_tool("get_verified_research_evidence")
        self.assertEqual(result["records"][0]["freshness"], "UNKNOWN")
        self.assertIn("not proof", result["policy"])


if __name__ == "__main__":
    unittest.main()
