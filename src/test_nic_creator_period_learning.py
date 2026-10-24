"""Tests for creator-period Write-to-Earn cohort learning."""
import unittest

from src.nic_creator_period_learning import build_learning_artifact


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
        self.assertEqual(creator["post_cohort_7d"]["post_count"], 1)
        self.assertEqual(creator["post_cohort_14d"]["post_count"], 2)
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

    def test_no_posts_does_not_turn_creator_reward_into_post_reward(self):
        self.posts_input["posts"] = []
        artifact = build_learning_artifact(self.leaderboard, self.posts_input, "2026-10-24T00:00:00Z")
        creator = artifact["creator_periods"][0]
        self.assertEqual(creator["post_cohort_7d"]["post_count"], 0)
        self.assertEqual(creator["creator_period_reward"]["amount"], 1000)
        self.assertEqual(creator["creator_period_reward"]["granularity"], "creator_period_only")


if __name__ == "__main__":
    unittest.main()
