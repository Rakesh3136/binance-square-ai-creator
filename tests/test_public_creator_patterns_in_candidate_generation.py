"""Tests that public creator benchmarks reach the writer as aggregate-only hypotheses."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("candidate_generation", ROOT / "src/candidate_generation_4.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_public_pattern_brief_uses_repeated_aggregate_patterns_only():
    source = {
        "sample_count": 42,
        "creator_count": 8,
        "performance_by_archetype": [
            {"archetype": "educational", "samples": 2, "reply_rate": 0.9},
            {"archetype": "data_onchain", "samples": 8, "confidence": "medium", "reply_rate": 0.08, "follower_rate": 0.02, "avg_views": 300, "avg_replies": 12},
        ],
        "format_counts": {"chart": 12, "data": 9},
        "our_baseline": {"samples": 5, "avg_views": 100},
        "reusable_rules": ["Learn patterns, not sentences."],
        "examples": [{"text": "DO NOT PASS THIS RAW POST TEXT TO THE WRITER"}],
    }
    brief = module.build_public_pattern_brief(source)
    assert brief["status"] == "PUBLIC_AGGREGATE_PATTERNS_AVAILABLE"
    assert [x["archetype"] for x in brief["top_archetypes_by_observed_reply_and_follower_rate"]] == ["data_onchain"]
    assert brief["sample_count"] == 42
    assert "examples" not in brief
    assert "DO NOT PASS THIS RAW POST TEXT TO THE WRITER" not in str(brief)
    assert any("not causal" in x.lower() or "observational" in x.lower() for x in brief["guardrails"])


def test_missing_public_patterns_fail_soft_without_inventing_evidence():
    brief = module.build_public_pattern_brief({})
    assert brief["status"] == "NO_PUBLIC_PATTERN_DATA"
    assert brief["top_archetypes_by_observed_reply_and_follower_rate"] == []
    assert brief["observed_format_counts"] == []

def test_public_pattern_brief_exposes_rolling_creator_research_without_earnings_claims():
    source = {
        "sample_count": 20,
        "creator_count": 5,
        "performance_by_archetype": [{"archetype": "education_explainer", "samples": 5, "reply_rate": 0.1}],
        "rolling_learning_windows": {
            "seven_day": {"window_days": 7, "dated_posts": 8, "performance_by_archetype": [{"archetype": "technical_chart", "samples": 4}]},
            "fourteen_day": {"window_days": 14, "dated_posts": 18, "performance_by_archetype": [{"archetype": "education_explainer", "samples": 7}]},
        },
        "research_limits": {"public_metrics_are_not_earnings": True},
    }
    brief = module.build_public_pattern_brief(source)
    assert brief["rolling_learning_windows"]["seven_day"]["dated_posts"] == 8
    assert brief["rolling_learning_windows"]["fourteen_day"]["window_days"] == 14
    assert brief["research_limits"]["public_metrics_are_not_earnings"] is True


def test_earnings_learning_is_sanitized_before_reaching_writer():
    earnings = {
        "schema": "NIC-SQUARE-EARNINGS-LEARNING-1.0",
        "weekly_earnings_goal": {"target_usdc": 200, "actual_verified_usdc_7d": 50.0},
        "creator_study_queue": [{
            "creator": "PRIVATE_CREATOR_NAME_MUST_NOT_REACH_WRITER",
            "sample_urls": ["https://private.example/post/123"],
        }],
        "best_public_format_hypotheses": [{
            "archetype": "education_explainer",
            "sample_count": 12,
            "window_days": 14,
            "avg_views": 450,
            "mean_public_engagement_rate": 0.04,
            "reply_rate": 0.01,
            "evidence_type": "PUBLIC_OBSERVATION_NOT_EARNINGS",
        }],
        "current_program_mechanics": {
            "relevant_trade_attribution": "Use a relevant verified cashtag or real widget.",
            "trade_commission_reward_window_days": 7,
            "text_content_engagement_bonus_window_days": 30,
            "engagement_bonus_signal": "Genuine comments, likes, follows and shares.",
            "anti_abuse_rule": "No artificial engagement.",
            "source_url": "https://www.binance.com/en/square/profile/binance_square_official",
        },
        "recommended_content_playbook": ["Write original, evidence-led content."],
    }
    brief = module.build_public_pattern_brief({"sample_count": 0}, earnings)
    safe = brief["earnings_learning"]
    assert safe["public_archetype_hypotheses"][0]["archetype"] == "education_explainer"
    assert safe["program_mechanics"]["trade_commission_reward_window_days"] == 7
    assert safe["program_mechanics"]["text_engagement_bonus_window_days"] == 30
    assert "PRIVATE_CREATOR_NAME_MUST_NOT_REACH_WRITER" not in str(safe)
    assert "private.example" not in str(safe)
    assert "weekly_earnings_goal" not in str(safe)
    assert "actual_verified_usdc_7d" not in str(safe)



def test_rolling_window_hides_individual_creator_rows_from_writer():
    source = {
        "sample_count": 50,
        "creator_count": 10,
        "format_counts": {"analysis": 15},
        "rolling_learning_windows": {
            "seven_day": {
                "window_days": 7,
                "dated_posts": 20,
                "distinct_creators": 8,
                "creator_candidates": [{
                    "creator": "DO_NOT_LEAK_CREATOR_NAME",
                    "creator_id": "private-user-id",
                    "sample_urls": ["https://example.invalid/private-post"],
                }],
                "performance_by_archetype": [{
                    "archetype": "education_explainer", "samples": 12, "avg_views": 450, "reply_rate": 0.02,
                }],
            },
            "fourteen_day": {"window_days": 14, "dated_posts": 40, "distinct_creators": 12},
        },
    }
    brief = module.build_public_pattern_brief(source)
    rolling = brief["rolling_learning_windows"]
    assert rolling["seven_day"]["performance_by_archetype"][0]["archetype"] == "education_explainer"
    assert "DO_NOT_LEAK_CREATOR_NAME" not in str(brief)
    assert "private-user-id" not in str(brief)
    assert "example.invalid/private-post" not in str(brief)


if __name__ == "__main__":
    test_public_pattern_brief_uses_repeated_aggregate_patterns_only()
    test_missing_public_patterns_fail_soft_without_inventing_evidence()
    test_public_pattern_brief_exposes_rolling_creator_research_without_earnings_claims()
    test_earnings_learning_is_sanitized_before_reaching_writer()
    test_rolling_window_hides_individual_creator_rows_from_writer()
