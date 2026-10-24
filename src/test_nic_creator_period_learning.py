"""Tests for creator-period Write-to-Earn cohort learning."""
import copy
import unittest

from src.nic_creator_period_learning import build_learning_artifact, _creator_match as runtime_name_match


class CreatorPeriodLearningTests(unittest.TestCase):
    def setUp(self):
        names = ["Creator A", "Creator B", "Creator C", "Creator D"]
        self.leaderboard = {
            "entries": [
                {
                    "creator": name,
                    "rank": index + 1,
                    "displayed_amount": amount,
                    "currency": "USDC",
                    "period_start": "2026-10-12T00:00:00Z",
                    "period_end": "2026-10-18T23:59:59Z",
                    "source_url": "https://www.binance.com/en/square/WriteToEarn",
                    "evidence_ref": "test-evidence",
                }
                for index, (name, amount) in enumerate(zip(names, [1000, 800, 300, 200]))
            ]
        }
        self.posts_input = {
            "creator_collections": [
                {
                    "creator": name,
                    "profile_url": f"https://www.binance.com/en/square/profile/{name.lower().replace(' ', '')}",
                    "identity_match": "verified",
                    "collection_status": "complete",
                    "window_7d_complete": True,
                    "window_14d_complete": True,
                }
                for name in names
            ],
            "posts": [],
        }
        for name in names:
            profile_url = f"https://www.binance.com/en/square/profile/{name.lower().replace(' ', '')}"
            for day, body in [
                ("2026-10-06T10:00:00Z", f"$BTC numeric evidence source link https://example.com. Risk if the level fails? {name}"),
                ("2026-10-13T10:00:00Z", f"$ETH market structure, volume 12,000, however the downside risk remains. {name}"),
                ("2026-10-14T10:00:00Z", f"$SOL numeric evidence and source https://example.com. The invalidation matters. {name}"),
                ("2026-10-15T10:00:00Z", f"$BNB participation and volume 5000, but the thesis can fail. {name}"),
            ]:
                self.posts_input["posts"].append({
                    "creator": name,
                    "creator_profile_url": profile_url,
                    "post_id": f"{name}-{day}",
                    "post_url": f"https://www.binance.com/en/square/post/{name}-{day}",
                    "published_at_utc": day,
                    "text": body,
                    "format": "text",
                    "topic": "market structure",
                    "source_urls": ["https://example.com"],
                })

    def test_period_rewards_remain_creator_level_and_windows_include_all_posts(self):
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["reward_granularity"], "creator_period")
        self.assertEqual(artifact["learning_status"], "COHORT_HYPOTHESES_READY")
        creator = artifact["creator_periods"][0]
        self.assertEqual(creator["post_cohort_7d"]["post_count"], 3)
        self.assertEqual(creator["post_cohort_14d"]["post_count"], 4)
        self.assertEqual(creator["post_cohort_14d"]["window_start_utc"], "2026-10-05T00:00:00+00:00")
        # The first day of the preceding week must not be clipped to 23:59:59.
        self.posts_input["posts"].append({
            "creator": "Creator A",
            "creator_profile_url": "https://www.binance.com/en/square/profile/creatora",
            "post_id": "Creator A-2026-10-05-boundary",
            "published_at_utc": "2026-10-05T00:00:00Z",
            "text": "Boundary post from the first day of the 14-day research window.",
            "format": "text",
            "topic": "market structure",
        })
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["creator_periods"][0]["post_cohort_14d"]["post_count"], 5)
        self.assertEqual(creator["creator_period_reward"]["amount"], 1000)
        self.assertEqual(creator["creator_period_reward"]["granularity"], "creator_period_only")
        self.assertIn("NOT attributed", creator["attribution_policy"])
        self.assertEqual(artifact["reward_tier_cohort_comparison"]["causal_claim"], "NOT_SUPPORTED_BY_CREATOR_PERIOD_REWARDS")

    def test_missing_complete_collection_blocks_reward_learning_claim(self):
        self.posts_input["creator_collections"][0]["window_7d_complete"] = False
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["coverage"]["complete_7d"], 3)
        self.assertEqual(artifact["learning_status"], "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE")

    def test_unverified_creator_identity_does_not_count_as_coverage(self):
        self.posts_input["creator_collections"][0]["identity_match"] = "candidate"
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["coverage"]["identity_verified"], 3)
        self.assertEqual(artifact["coverage"]["complete_7d"], 3)

    def test_all_7d_posts_but_one_missing_14d_window_blocks_learning(self):
        self.posts_input["creator_collections"][0]["window_14d_complete"] = False
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["coverage"]["complete_7d"], 4)
        self.assertEqual(artifact["coverage"]["complete_14d"], 3)
        self.assertEqual(artifact["learning_status"], "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE")
        self.assertEqual(
            artifact["reward_tier_cohort_comparison"]["status"],
            "BLOCKED_NEED_AT_LEAST_80_PERCENT_VERIFIED_CREATOR_WINDOWS",
        )
        self.assertEqual(artifact["coverage_status"], "PARTIAL_OR_BLOCKED_LEADERBOARD_COVERAGE")

    def test_nine_of_ten_verified_creator_cohorts_can_produce_cautious_learning(self):
        leaderboard = copy.deepcopy(self.leaderboard)
        post_input = copy.deepcopy(self.posts_input)
        for index in range(6):
            name = f"Extra Creator {index + 1}"
            profile_url = f"https://www.binance.com/en/square/profile/extra{index + 1}"
            leaderboard["entries"].append({
                "creator": name, "rank": index + 5, "displayed_amount": [700, 600, 500, 400, 300, 100][index],
                "currency": "USDC", "period_start": "2026-10-12T00:00:00Z",
                "period_end": "2026-10-18T23:59:59Z",
                "source_url": "https://www.binance.com/en/square/WriteToEarn",
                "evidence_ref": "test-evidence",
            })
            # The tenth creator deliberately remains unresolved. Never fabricate a profile or posts.
            if index == 5:
                continue
            post_input["creator_collections"].append({
                "creator": name, "profile_url": profile_url, "identity_match": "verified",
                "collection_status": "complete", "window_7d_complete": True, "window_14d_complete": True,
            })
            for day, body in [
                ("2026-10-06T10:00:00Z", f"$BTC volume and risk boundary for {name}"),
                ("2026-10-13T10:00:00Z", f"$ETH evidence 12,000 volume and invalidation for {name}"),
                ("2026-10-14T10:00:00Z", f"$SOL structure and source https://example.com for {name}"),
                ("2026-10-15T10:00:00Z", f"$BNB market context, but the thesis can fail for {name}"),
            ]:
                post_input["posts"].append({
                    "creator": name, "creator_profile_url": profile_url,
                    "post_id": f"{name}-{day}", "post_url": f"https://www.binance.com/en/square/post/{name}-{day}",
                    "published_at_utc": day, "text": body, "format": "text",
                    "topic": "market structure", "source_urls": ["https://example.com"],
                })

        artifact = build_learning_artifact(leaderboard, post_input, "2026-10-24T00:00:00Z")
        self.assertEqual(artifact["coverage"]["leaderboard_creators"], 10)
        self.assertEqual(artifact["coverage"]["complete_7d"], 9)
        self.assertEqual(artifact["coverage"]["complete_14d"], 9)
        self.assertEqual(artifact["learning_status"], "COHORT_HYPOTHESES_READY")
        self.assertEqual(artifact["coverage_status"], "PARTIAL_OR_BLOCKED_LEADERBOARD_COVERAGE")
        self.assertEqual(artifact["learning_coverage_policy"]["creators_complete_for_both_windows"], 9)
        self.assertIn("full leaderboard coverage remains incomplete", artifact["learning_coverage_policy"]["partial_coverage_warning"])
        self.assertEqual(
            artifact["reward_tier_cohort_comparison"]["status"],
            "DESCRIPTIVE_COMPARISON_AVAILABLE",
        )

    def test_no_posts_does_not_turn_creator_reward_into_post_reward(self):
        self.posts_input["posts"] = []
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        creator = artifact["creator_periods"][0]
        self.assertEqual(creator["post_cohort_7d"]["post_count"], 0)
        self.assertEqual(creator["creator_period_reward"]["amount"], 1000)
        self.assertEqual(creator["creator_period_reward"]["granularity"], "creator_period_only")


    def test_non_latin_creator_names_and_case_variant_profile_urls_match_posts(self):
        leaderboard = {"entries": [{
            "creator": "小二哥哥68", "rank": 1, "displayed_amount": 557.94,
            "currency": "USDC", "period_start": "2026-10-12T00:00:00Z",
            "period_end": "2026-10-18T23:59:59Z",
            "source_url": "https://www.binance.com/en/square/WriteToEarn",
        }]}
        profile_url = "https://www.binance.com/en/square/profile/xiaoer2"
        post_input = {
            "creator_collections": [{
                "creator": "小二哥哥68", "profile_url": profile_url,
                "identity_match": "verified", "collection_status": "complete",
                "window_7d_complete": True, "window_14d_complete": True,
            }],
            "posts": [{
                "creator": "小二哥哥68",
                "creator_profile_url": "https://www.binance.com/en/square/profile/Xiaoer2/",
                "post_id": "cn-post-1",
                "posted_at": "2026-10-13T10:00:00Z",
                "text": "$BTC 12,000 volume and a clear risk boundary?",
                "format": "text",
            }],
        }
        artifact = build_learning_artifact(leaderboard, post_input, "2026-10-24T00:00:00Z")
        creator = artifact["creator_periods"][0]
        self.assertEqual(creator["post_cohort_7d"]["post_count"], 1)
        self.assertEqual(creator["post_cohort_14d"]["post_count"], 1)
        self.assertEqual(artifact["coverage"]["identity_verified"], 1)

    def test_arabic_creator_identity_is_not_erased_by_normalization(self):
        self.assertTrue(runtime_name_match("محترف عملات رقميه", "محترف عملات رقميه"))
        self.assertFalse(runtime_name_match("محترف عملات رقميه", "Btc星辰"))


if __name__ == "__main__":
    unittest.main()
