import unittest

from src.nic_rewarded_format_learning import build_owner_rewarded_format_brief


class RewardedFormatLearningTests(unittest.TestCase):
    def test_converts_owner_reported_setup_to_safe_transferable_features(self):
        brief = build_owner_rewarded_format_brief({
            "376457571598023": {
                "amount_usdc": 0.77,
                "event_count": 1,
                "content_metadata": {
                    "content_lane": "technical_setup",
                    "content_format": "4h_chart_annotated_setup",
                    "asset_symbol": "US",
                    "timeframe": "4H",
                    "chart_type": "annotated_candlestick",
                    "setup_structure": "retraced into demand zone at 0.010000-0.011500",
                    "confirmation_condition": "hold demand zone",
                    "invalidation_condition": "close below 0.009500",
                    "entry_zone": "0.010000-0.011500",
                    "target_levels": ["0.020000", "0.030000"],
                    "public_post_url": "https://example.invalid/post/123456",
                },
            }
        })
        self.assertEqual(brief["status"], "OWNER_REPORTED_FORMAT_HYPOTHESIS_AVAILABLE")
        self.assertTrue(brief["not_a_verified_reward_label"])
        self.assertEqual(brief["examples"][0]["confidence"], "LOW_SINGLE_SAMPLE")
        self.assertIn("state a concrete invalidation/falsification condition", brief["examples"][0]["transferable_features"])
        serialized = str(brief)
        for forbidden in ("0.77", "376457571598023", "0.010000", "0.009500", "0.020000", "example.invalid", "US"):
            self.assertNotIn(forbidden, serialized)

    def test_empty_ledger_returns_neutral_status(self):
        brief = build_owner_rewarded_format_brief({})
        self.assertEqual(brief["status"], "NO_OWNER_REPORTED_FORMAT_EXAMPLES")
        self.assertEqual(brief["examples"], [])


if __name__ == "__main__":
    unittest.main()
