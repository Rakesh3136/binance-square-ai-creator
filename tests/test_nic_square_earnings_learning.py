import unittest
from datetime import datetime, timezone

from src.nic_square_earnings_learning import build_learning_plan, collect_verified_rewards, summarize_own_content, analyze_public_reward_claims, summarize_owner_reported_reward_feedback, build_learning_memory_entry, build_autonomy_readiness


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

    def test_owner_reported_exact_post_reward_feeds_learning_but_not_verified_totals(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        event = {
            "event_id": "owner-report-374795126927596-20261021-01",
            "post_id": "374795126927596",
            "reward_amount_usdc": 0.201,
            "currency": "USDC",
            "reported_at": "2026-10-21T11:16:00+05:30",
            "report_source": "ACCOUNT_OWNER_REPORTED",
            "verification_status": "OWNER_REPORTED",
            "content_metadata": {
                "content_lane": "long_term_thesis",
                "content_format": "text_plus_image",
                "hook_type": "long_term_conviction_with_target",
                "summary": "QNT long-term thesis",
                "owner_reported_views": 5100,
                "public_post_url": "https://www.binance.com/en/square/post/374795126927596",
            },
        }
        feedback = summarize_owner_reported_reward_feedback([event], now)
        self.assertEqual(feedback["status"], "OWNER_REPORTED_FEEDBACK_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED")
        self.assertAlmostEqual(feedback["7_day"]["reported_usdc"], 0.201)
        self.assertEqual(feedback["7_day"]["post_count"], 1)
        self.assertFalse(feedback["independently_verified"])
        self.assertFalse(feedback["included_in_verified_reward_totals"])
        self.assertEqual(feedback["entries"][0]["post_id"], "374795126927596")
        self.assertEqual(feedback["entries"][0]["owner_reported_views"], 5100)

        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=now, owner_reported_reward_events=[event],
        )
        self.assertIsNone(plan["verified_reward_evidence"]["verified_usdc_7d"])
        self.assertEqual(plan["verified_reward_evidence"]["accepted_unique_reward_events_7d"], 0)
        self.assertAlmostEqual(plan["owner_reported_reward_feedback"]["7_day"]["reported_usdc"], 0.201)

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
        performance = [{"canonical_post_id": "374795126927596", "collected_at": "2026-10-21T10:00:00+00:00", "metrics": {"views": 5100, "likes": 51, "comments": 7, "shares": 3, "follows": 2}}]
        summary = summarize_own_content(now, attribution, performance)
        seven = summary["7_day"]
        self.assertEqual(seven["posts"], 1)
        self.assertEqual(seven["total_views"], 5100)
        self.assertGreater(seven["weighted_engagement_per_1000_views"], 0)
        self.assertEqual(seven["total_follows"], 2)
        self.assertEqual(seven["follow_metric_coverage_posts"], 1)
        self.assertIsNotNone(seven["follow_rate_per_view"])



    def test_missing_follow_metrics_are_unknown_not_zero(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        attribution = [{"canonical_post_id": "374795126927596", "published_at": "2026-10-18T10:00:00+00:00", "category": "research"}]
        performance = [{"canonical_post_id": "374795126927596", "collected_at": "2026-10-21T10:00:00+00:00", "metrics": {"views": 100, "likes": 3, "comments": 1, "shares": 0}}]
        summary = summarize_own_content(now, attribution, performance)["7_day"]
        self.assertIsNone(summary["total_follows"])
        self.assertIsNone(summary["follow_rate_per_view"])
        self.assertEqual(summary["follow_metric_coverage_posts"], 0)

    def test_public_earnings_claims_are_discovered_but_never_verified_as_payouts(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        examples = [
            {"creator": "ClaimingCreator", "creator_id": "creator-1", "post_id": "379000000000001",
             "posted_at": "2026-10-20T10:00:00+00:00",
             "source_url": "https://www.binance.com/en/square/post/379000000000001",
             "text": "I earned 200 USDC from Write to Earn this week!"},
            {"creator": "OldClaim", "creator_id": "creator-2", "post_id": "379000000000002",
             "posted_at": "2026-09-20T10:00:00+00:00",
             "source_url": "https://www.binance.com/en/square/post/379000000000002",
             "text": "I earned 500 USDC this week."},
            {"creator": "UndatedClaim", "creator_id": "creator-3", "post_id": "379000000000003",
             "source_url": "https://www.binance.com/en/square/post/379000000000003",
             "text": "I earned 400 USDC from Write to Earn."},
        ]
        result = analyze_public_reward_claims(examples, now)
        self.assertEqual(result["public_claim_post_count"], 1)
        self.assertEqual(result["distinct_claiming_creators"], 1)
        self.assertEqual(result["claims"][0]["creator"], "ClaimingCreator")
        self.assertEqual(result["claims"][0]["earnings_status"], "UNVERIFIED_PUBLIC_SELF_REPORT")
        self.assertEqual(result["claims"][0]["evidence_type"], "PUBLIC_CLAIM_NOT_PAYMENT_PROOF")
        self.assertEqual(result["undated_claims_excluded"], 1)



    def test_creator_research_queue_balances_styles_and_keeps_earnings_claims_separate(self):
        benchmark = benchmark_fixture()
        seven = benchmark["rolling_learning_windows"]["seven_day"]
        fourteen = benchmark["rolling_learning_windows"]["fourteen_day"]
        second = {
            "creator": "ChartCreator", "creator_id": "chart-creator-id", "posts": 6,
            "mean_public_engagement_rate": 0.04, "median_views": 500, "avg_views": 550,
            "reply_rate": 0.01, "share_rate": 0.02, "dominant_archetypes": ["technical_chart"],
            "sample_urls": ["https://www.binance.com/en/square/post/378834646947380"],
            "earnings_status": "NOT_PUBLICLY_VERIFIED",
        }
        seven["top_by_public_engagement"] = [benchmark_fixture()["rolling_learning_windows"]["seven_day"]["top_by_public_engagement"][0], second]
        fourteen["top_by_public_engagement"] = [benchmark_fixture()["rolling_learning_windows"]["fourteen_day"]["top_by_public_engagement"][0], second]
        examples = [{
            "creator": "SelfReportedCreator", "creator_id": "claim-creator-id",
            "post_id": "379000000000001", "posted_at": "2026-10-20T10:00:00+00:00",
            "source_url": "https://www.binance.com/en/square/post/379000000000001",
            "text": "I earned 200 USDC from Write to Earn this week!",
        }]
        plan = build_learning_plan(benchmark, {}, [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc), public_examples=examples)
        queue = plan["creator_study_queue"]
        self.assertEqual({row["creator_id"] for row in queue}, {"public-creator-id", "chart-creator-id"})
        self.assertIn("technical_chart", plan["creator_research_coverage"]["represented_archetypes"])
        self.assertEqual(plan["self_reported_earnings_creator_study_queue"][0]["earnings_status"], "UNVERIFIED_PUBLIC_SELF_REPORT")
        self.assertNotIn("SelfReportedCreator", [row["creator"] for row in queue])
        self.assertFalse(plan["learning_policy"]["do_not_infer_private_creator_earnings"] is False)


    def test_public_leaderboard_amounts_and_creator_names_become_research_leads(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        examples = [{"creator": "Binance Square Official", "creator_id": "official", "post_id": "379000000000010", "posted_at": "2026-10-20T10:00:00+00:00", "source_url": "https://www.binance.com/en/square/post/379000000000010", "text": "Write to Earn weekly leaderboard: @AlphaCreator - $800 USDC; @BetaCreator 💰 500 USDC"}]
        result = analyze_public_reward_claims(examples, now)
        entries = result["public_leaderboard_entries"]
        self.assertEqual({row["claimed_creator"] for row in entries}, {"AlphaCreator", "BetaCreator"})
        self.assertEqual({row["claimed_amount"] for row in entries}, {800.0, 500.0})
        self.assertTrue(all(row["earnings_status"] == "PUBLIC_LEADERBOARD_CLAIM_NOT_INDEPENDENTLY_VERIFIED" for row in entries))
        plan = build_learning_plan(benchmark_fixture(), {}, [], now=now, public_examples=examples)
        self.assertGreaterEqual(len(plan["public_earnings_leaderboard_study_queue"]), 2)
        self.assertEqual(plan["observed_wte_leaderboard_entries_count"], 0)
        self.assertTrue(plan["leaderboard_research_coverage"]["amounts_are_not_payout_proof"])
        readiness = build_autonomy_readiness(
            plan,
            {"status": "PUBLIC_POSTS_CHECKED_NO_RECENT_CLAIMS", "retained_recent_claim_post_count": 0},
            {"editorial_auto_publication_enabled": False, "requires_human_review_for_editorial": True},
        )
        self.assertEqual(readiness["capabilities"]["other_creator_weekly_reward_source"]["status"], "BLOCKED_NO_AUTHORIZED_SOURCE")

    def test_observed_leaderboard_entries_flow_into_creator_study_queue(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        observed = [{
            "creator": "LeaderboardCreator",
            "creator_profile_url": "https://www.binance.com/en/square/profile/LeaderboardCreator",
            "rank": 3,
            "displayed_amount": 800.0,
            "currency": "USDC",
            "period_start": "2026-10-12T00:00:00+00:00",
            "period_end": "2026-10-18T23:59:00+00:00",
            "observed_at": "2026-10-21T10:00:00+00:00",
            "source_url": "https://www.binance.com/en/square/WriteToEarn",
            "evidence_ref": "capture://leaderboard-row-3",
            "earnings_status": "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT",
        }]
        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=now, observed_leaderboard_entries=observed,
        )
        queue = plan["public_earnings_leaderboard_study_queue"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["creator"], "LeaderboardCreator")
        self.assertEqual(queue[0]["claimed_amount"], 800.0)
        self.assertEqual(queue[0]["creator_profile_url"], "https://www.binance.com/en/square/profile/LeaderboardCreator")
        self.assertEqual(queue[0]["evidence_ref"], "capture://leaderboard-row-3")
        self.assertEqual(queue[0]["earnings_status"], "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT")
        self.assertTrue(plan["leaderboard_research_coverage"]["amounts_are_not_payout_proof"])

    def test_profile_research_enriches_creator_study_queue_without_claiming_earnings(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        profile_research = {
            "status": "PROFILE_RESEARCH_COMPLETE",
            "public_only": True,
            "authenticated_session_used": False,
            "candidate_count": 1,
            "profiles_resolved": 1,
            "profile_resolution_failures": 0,
            "posts_collected_7d": 2,
            "posts_collected_8_to_14d": 1,
            "posts_collected_14d": 3,
            "seven_day_coverage_observed": True,
            "fourteen_day_coverage_observed": True,
            "profiles": [{
                "creator": "PublicCreator",
                "username": "public_creator",
                "display_name": "Public Creator",
                "creator_profile_url": "https://www.binance.com/en/square/profile/public_creator",
                "discovery_source": "public_performance_benchmark",
                "earnings_status": "PUBLIC_RESEARCH_LEAD_NOT_VERIFIED",
                "posts_7d": 2,
                "posts_14d": 3,
                "recent_post_samples": [{"post_url": "https://www.binance.com/en/square/post/12345", "posted_at": "2026-10-20T10:00:00+00:00", "archetype": "education_explainer"}],
            }],
            "posts": [],
        }
        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=now, creator_profile_research=profile_research,
        )
        self.assertEqual(plan["creator_profile_research"]["status"], "PROFILE_RESEARCH_COMPLETE")
        self.assertEqual(plan["creator_profile_research"]["profiles_resolved"], 1)
        self.assertEqual(plan["research_coverage"]["status"], "FULL_7_AND_14_DAY_PROFILE_COVERAGE")
        self.assertEqual(plan["research_coverage"]["public_feed_status"], "FULL_7_AND_14_DAY_COVERAGE")
        self.assertTrue(plan["research_coverage"]["profile_coverage_observed"])
        profile_queue = plan["creator_profile_study_queue"]
        self.assertEqual(profile_queue[0]["creator_profile_url"], "https://www.binance.com/en/square/profile/public_creator")
        public_queue = plan["creator_study_queue"]
        self.assertEqual(public_queue[0]["creator_profile_url"], "https://www.binance.com/en/square/profile/public_creator")
        self.assertFalse(plan["creator_profile_research"]["authenticated_session_used"])
        self.assertEqual(profile_queue[0]["evidence_type"], "PUBLIC_PROFILE_RESEARCH_NOT_EARNINGS")

    def test_learning_memory_persists_owner_feedback_and_profile_coverage_separately(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=now,
            owner_reported_reward_events=[{
                "event_id": "owner-report-1", "post_id": "374795126927596",
                "reward_amount_usdc": 0.201, "currency": "USDC",
                "reported_at": "2026-10-21T11:16:00+05:30",
                "content_metadata": {"content_lane": "long_term_thesis",
                    "public_post_url": "https://www.binance.com/en/square/post/374795126927596"},
            }],
            creator_profile_research={
                "status": "PROFILE_RESEARCH_COMPLETE", "profiles_resolved": 12,
                "posts_collected_7d": 172, "posts_collected_8_to_14d": 38,
            },
        )
        row = build_learning_memory_entry(plan, now)
        self.assertEqual(row["creator_profiles_resolved"], 12)
        self.assertEqual(row["profile_posts_8_to_14d"], 38)
        self.assertAlmostEqual(row["owner_reported_usdc_7d"], 0.201)
        self.assertEqual(row["owner_reported_reward_events_7d"], 1)
        self.assertTrue(row["owner_reported_feedback_is_not_verified"])
        self.assertIsNone(row["verified_usdc_7d"])

    def test_autonomy_readiness_names_private_reward_and_exact_post_proof_blockers(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        plan = build_learning_plan(
            benchmark_fixture(), {}, [], now=now,
            creator_profile_research={
                "status": "PROFILE_RESEARCH_COMPLETE",
                "profiles_resolved": 12,
                "posts_collected_7d": 173,
                "posts_collected_8_to_14d": 47,
                "seven_day_coverage_observed": True,
                "fourteen_day_coverage_observed": True,
                "public_only": True,
            },
        )
        readiness = build_autonomy_readiness(
            plan,
            {"status": "HASHTAG_PAGES_READ_NO_RECENT_DATED_CLAIM_POSTS",
             "public_corpus_rows_checked": 2255, "retained_recent_claim_post_count": 0},
            {"editorial_auto_publication_enabled": False, "requires_human_review_for_editorial": True},
        )
        self.assertEqual(readiness["status"], "PUBLIC_RESEARCH_READY_PRIVATE_REWARD_SOURCE_BLOCKED")
        self.assertFalse(readiness["full_autonomy_proven"])
        self.assertEqual(readiness["capabilities"]["public_creator_profile_research"]["profiles_resolved"], 12)
        self.assertEqual(readiness["capabilities"]["other_creator_weekly_reward_source"]["status"], "BLOCKED_NO_AUTHORIZED_SOURCE")
        self.assertEqual(readiness["capabilities"]["own_post_reward_attribution"]["status"], "BLOCKED_NO_VERIFIED_POST_LINKED_REWARD")
        self.assertFalse(readiness["capabilities"]["automatic_publication"]["enabled_by_policy"])
        self.assertTrue(readiness["capabilities"]["automatic_publication"]["human_review_required"])
        blocker_ids = {row["id"] for row in readiness["blockers"]}
        self.assertIn("other_creator_paid_reward_source", blocker_ids)
        self.assertIn("own_post_reward_attribution", blocker_ids)
        self.assertIn("public_reward_claim_leads", blocker_ids)

    def test_wte_strategy_covers_rewarded_formats_and_policy_drives_auto_post_flag(self):
        plan = build_learning_plan(benchmark_fixture(), {}, [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
        mechanics = plan["current_program_mechanics"]
        formats = mechanics["format_reward_map"]
        self.assertIn("engagement bonus", formats["short_text_posts"])
        self.assertIn("engagement bonus", formats["long_articles"])
        self.assertIn("top 100", formats["livestreams"])
        self.assertIn("Basic commission", formats["chats"])
        strategy = plan["creator_format_strategy"]
        self.assertGreaterEqual(len(strategy["priority"]), 3)
        self.assertIn("genuine", strategy["engagement_design"].lower())
        self.assertTrue(plan["learning_policy"]["automatic_posting_enabled"])

    def test_new_write_to_earn_rules_have_separate_october_19_cohort(self):
        plan = build_learning_plan(benchmark_fixture(), {}, [], now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc))
        mechanics = plan["current_program_mechanics"]
        self.assertEqual(mechanics["engagement_bonus_effective_at"], "2026-10-19T00:00:00+00:00")
        self.assertEqual(mechanics["engagement_bonus_settlement_period_days"], 7)
        self.assertEqual(mechanics["trade_commission_reward_window_days"], 7)
        self.assertEqual(mechanics["engagement_reward_window_days"], 30)
        self.assertIn("evaluate posts published from 2026-10-19 separately", mechanics["rules_change_cohort_policy"])


    def test_public_posts_by_leaderboard_creators_are_summarized_in_7_and_14_day_windows(self):
        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        examples = [
            {"creator": "AlphaCreator", "posted_at": "2026-10-20T10:00:00+00:00", "archetype": "education_explainer", "format": "text", "views": 1000, "likes": 50, "replies": 10, "shares": 5},
            {"creator": "AlphaCreator", "posted_at": "2026-10-10T10:00:00+00:00", "archetype": "technical_chart", "format": "chart", "views": 2000, "likes": 60, "replies": 8, "shares": 4},
            {"creator": "OtherCreator", "posted_at": "2026-10-20T10:00:00+00:00", "archetype": "general", "views": 9000, "likes": 900, "replies": 90, "shares": 90},
        ]
        entries = [{"claimed_creator": "AlphaCreator", "claimed_amount": 800}]
        from src.nic_square_earnings_learning import summarize_leaderboard_creator_posts
        result = summarize_leaderboard_creator_posts(examples, entries, now)
        self.assertEqual(result["seven_day"]["matched_posts"], 1)
        self.assertEqual(result["fourteen_day"]["matched_posts"], 2)
        self.assertEqual(result["posts_age_8_to_14_days"], 1)
        self.assertEqual(result["fourteen_day"]["top_archetypes"][0]["archetype"], "education_explainer")
        self.assertTrue(result["public_metrics_are_not_earnings"])

if __name__ == "__main__":
    unittest.main()
