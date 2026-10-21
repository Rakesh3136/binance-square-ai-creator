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
