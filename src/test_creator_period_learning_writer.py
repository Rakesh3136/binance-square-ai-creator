"""Regression tests proving creator-period cohort hypotheses reach NIC's writer."""
from __future__ import annotations

import unittest

from src import nic_native_writer


def context_with_learning(learning):
    return {
        "preflight": {
            "selected_opportunity": {
                "symbol": "BTCUSDT",
                "category": "research_insight",
                "adjusted_score": 0.7,
            },
            "script_director_4": {"story_type": "research_edge"},
        },
        "publication": {"symbol": "BTCUSDT", "category": "research_insight"},
        "market": {
            "top_content_signals": [{
                "symbol": "BTCUSDT",
                "last_price": 67000,
                "price_change_percent": 1.2,
                "quote_volume_usdt": 1200000,
                "candles_1h": [],
            }],
        },
        "news": {},
        "creator_strategy_runtime": {"strategy_id": "evidence_led_research"},
        "creator_period_learning": learning,
    }


class CreatorPeriodLearningWriterTests(unittest.TestCase):
    def test_valid_cohort_hypothesis_is_consumed_without_post_level_attribution(self):
        learning = {
            "learning_status": "COHORT_HYPOTHESES_READY",
            "reward_tier_cohort_comparison": {
                "status": "DESCRIPTIVE_COMPARISON_AVAILABLE",
                "high_reward_creator_periods": {
                    "cohort": {
                        "post_count": 8,
                        "rates": {"has_source_link": 0.8, "has_numeric_evidence": 0.8},
                    },
                },
                "lower_reward_creator_periods": {
                    "cohort": {
                        "post_count": 8,
                        "rates": {"has_source_link": 0.2, "has_numeric_evidence": 0.2},
                    },
                },
            },
        }
        result = nic_native_writer.build(context_with_learning(learning))
        self.assertTrue(result["native_writer"]["creator_period_learning_applied"])
        self.assertEqual(result["native_writer"]["creator_period_learning_rule"], "evidence_led")
        self.assertEqual(result["native_writer"]["creator_period_reward_granularity"], "creator_period_only")

    def test_actual_high_earner_question_and_risk_pattern_is_applied(self):
        learning = {
            "learning_status": "COHORT_HYPOTHESES_READY",
            "reward_tier_cohort_comparison": {
                "status": "DESCRIPTIVE_COMPARISON_AVAILABLE",
                "high_reward_creator_periods": {
                    "cohort": {
                        "post_count": 653,
                        "rates": {
                            "has_question": 0.5559,
                            "has_risk_or_invalidation_language": 0.5176,
                            "has_numeric_evidence": 0.7734,
                        },
                    },
                },
                "lower_reward_creator_periods": {
                    "cohort": {
                        "post_count": 977,
                        "rates": {
                            "has_question": 0.087,
                            "has_risk_or_invalidation_language": 0.1054,
                            "has_numeric_evidence": 0.7666,
                        },
                    },
                },
            },
        }
        context = context_with_learning(learning)
        context["publication"]["timing_state"] = "EXHAUSTED"
        result = nic_native_writer.build(context)
        self.assertTrue(result["native_writer"]["creator_period_learning_applied"])
        self.assertEqual(
            result["native_writer"]["creator_period_learning_rule"],
            "risk_aware_discussion",
        )
        self.assertIn("Trader test:", result["draft"]["text"])
        self.assertEqual(result["draft"]["text"].count("?"), 1)
        self.assertEqual(
            result["native_writer"]["creator_period_reward_granularity"],
            "creator_period_only",
        )

    def test_incomplete_cohort_does_not_claim_reward_learning_applied(self):
        result = nic_native_writer.build(context_with_learning({
            "learning_status": "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE",
            "reward_tier_cohort_comparison": {
                "status": "BLOCKED_NEED_ALL_LEADERBOARD_CREATOR_WINDOWS_COMPLETE",
            },
        }))
        self.assertFalse(result["native_writer"]["creator_period_learning_applied"])
        self.assertEqual(
            result["native_writer"]["creator_period_learning_status"],
            "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE",
        )


if __name__ == "__main__":
    unittest.main()
