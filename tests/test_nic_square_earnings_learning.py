import unittest
from datetime import datetime, timezone

from src.nic_square_earnings_learning import build_learning_plan, collect_verified_rewards, summarize_own_content


def valid_reward_event():
    return {
        "event_id": "wte-verified-001",
        "canonical_post_id": "374795126927596",
        "observed_at": "2026-10-21T10:00:00+00:00",
        "verified_at": "2026-10-21T10:05:00+00:00",
        "reward_amount_usdc": 0.201,
        "currency": "USDC",
        "verified": True,
        "reward_status": "PAID_VERIFIED",
        "source": "test_fixture",
        "evidence_refs": [{
            "source_id": "reward-export-row-001",
            "sha256": "a" * 64,
            "observed_at": "2026-10-21T10:05:00+00:00",
        }],
    }


def benchmark_fixture():
    creator = {
        "creator": "PublicCreator",
        "creator_id": "public-creator-id",
        "posts": 5,
        "mean_public_engagement_rate": 0.08,
        "median_views": 800,
        "avg_views": 900,
        "reply_rate": 0.02,
        "share_rate": 0.01,
        "dominant_archetypes": ["education_explainer"],
        "sample_urls": ["https://www.binance.com/en/square/post/378834646947379"],
        "earnings_status": "NOT_PUBLICLY_VERIFIED",
    }
    return {
        "status": "PUBLIC_BENCHMARKS_AVAILABLE",
        "public_posts_collected_this_run": 50,
        "public_posts_observed": 500,
        "distinct_public_creators": 70,
        "metric_history": {"observations_retained": 1200, "retention_days": 21},
        "rolling_learning_windows": {
            "seven_day": {
                "window_days": 7,
                "dated_posts": 80,
                "coverage": {"posts_age_8_to_14_days": 0},
                "top_by_public_engagement": [creator],
                "top_by_discussion_and_shares": [creator],
                "top_by_median_reach": [creator],
                "performance_by_archetype": [{"archetype": "education_explainer", "samples": 8, "avg_views": 900, "mean_public_engagement_rate": 0.08, "reply_rate": 0.02, "avg_replies": 12}],
            },
            "fourteen_day": {
                "window_days": 14,
                "dated_posts": 140,
                "coverage": {"posts_age_8_to_14_days": 60},
                "top_by_public_engagement": [creator],
                "top_by_discussion_and_shares": [creator],
                "top_by_median_reach": [creator],
                "performance_by_archetype": [
                    {"archetype": "education_explainer", "samples": 18, "avg_views": 900, "mean_public_engagement_rate": 0.08, "reply_rate": 0.02, "avg_replies": 12},
                    {"archetype": "technical_chart", "samples": 6, "avg_views": 400, "mean_public_engagement_rate": 0.04, "reply_rate": 0.01, "avg_replies": 3},
                ],
            },
        },
    }


class SquareEarningsLearningTests(unittest.TestCase):
    def test_target_is_goal_not_guarantee_and_public_metrics_are_not_revenue(self):
        plan = build_learning_plan(
            benchmark_fixture(), {"our_baseline": {"samples": 8, "avg_views": 100}},
            [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc), target_usdc=200,
        )
        self.assertEqual(plan["weekly_earnings_goal"]["target_usdc"], 200)
        self.assertEqual(plan["weekly_earnings_goal"]["goal_type"], "OPTIMIZATION_TARGET_NOT_FORECAST")
        self.assertFalse(plan["weekly_earnings_goal"]["guaranteed"])
        self.assertIsNone(plan["weekly_earnings_goal"]["actual_verified_usdc_7d"])
        self.assertFalse(plan["research_coverage"]["public_views_or_engagement_are_earnings_evidence"])
        self.assertEqual(plan["historical_own_account_baseline"]["samples"], 8)

    def test_only_exact_post_source_backed_paid_events_count_as_verified_earnings(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        unattributed = {
            "event_id": "notification-1",
            "observed_at": "2026-10-21",
            "reward_amount_usdc": 50,
            "currency": "USDC",
            "verified": True,
            "detail_status": "VERIFIED_REWARD_UNATTRIBUTED_POST",
        }
        summary = collect_verified_rewards([unattributed, valid_reward_event()], now)
        self.assertEqual(summary["accepted_unique_reward_events_7d"], 1)
        self.assertAlmostEqual(summary["verified_usdc_7d"], 0.201)
        self.assertEqual(summary["rejected_events"], 1)
        self.assertTrue(summary["exact_post_attribution_required"])
        self.assertFalse(summary["public_metrics_used_as_revenue"])

    def test_studies_multiple_creator_segments_without_claiming_they_earn(self):
        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
        )
        queue = plan["creator_study_queue"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["creator"], "PublicCreator")
        self.assertEqual(queue[0]["posts_observed"], 5)
        self.assertEqual(queue[0]["earnings_status"], "NOT_PUBLICLY_VERIFIED")
        self.assertGreaterEqual(len(plan["best_public_format_hypotheses"]), 2)
        self.assertEqual(plan["best_public_format_hypotheses"][0]["evidence_type"], "PUBLIC_OBSERVATION_NOT_EARNINGS")
        self.assertTrue(plan["learning_policy"]["do_not_infer_private_creator_earnings"])

    def test_reports_missing_8_to_14_day_coverage_instead_of_pretending_it_exists(self):
        benchmark = benchmark_fixture()
        benchmark["rolling_learning_windows"]["fourteen_day"]["coverage"]["posts_age_8_to_14_days"] = 0
        plan = build_learning_plan(benchmark, {}, [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
        self.assertEqual(plan["research_coverage"]["status"], "14_DAY_SAMPLE_GAP_KEEP_COLLECTING")

    def test_own_account_metrics_use_nested_square_performance_schema(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        attribution = [{"canonical_post_id": "374795126927596", "published_at": "2026-10-18T10:00:00+00:00", "category": "research"}]
        performance = [{"canonical_post_id": "374795126927596", "collected_at": "2026-10-21T10:00:00+00:00", "metrics": {"views": 5100, "likes": 51, "comments": 7, "shares": 3}}]
        summary = summarize_own_content(now, attribution, performance)
        seven = summary["7_day"]
        self.assertEqual(seven["posts"], 1)
        self.assertEqual(seven["total_views"], 5100)
        self.assertGreater(seven["weighted_engagement_per_1000_views"], 0)


if __name__ == "__main__":
    unittest.main()
