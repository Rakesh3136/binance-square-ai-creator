import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publication_context", ROOT / "src" / "publication_context.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_synced_exhausted_timing_overrides_stale_technical_setup_lane():
    frozen = {"symbol": "HOT", "category": "technical_setup", "instruction": "Old setup instruction"}
    preflight = {
        "selected_opportunity": {
            "symbol": "HOT",
            "category": "research_insight",
            "instruction": "Old frozen instruction",
        },
        "editorial_authoritative_handoff": {
            "status": "SYNCED",
            "symbol": "HOT",
            "timing_state": "EXHAUSTED",
        },
    }
    eligibility = {
        "selected": {
            "symbol": "HOT",
            "category": "research_insight",
            "timing_state": "EXHAUSTED",
            "timing_reason": "Move is too extended for a fresh entry.",
        }
    }
    result = module.resolve_editorial_state(frozen, preflight, eligibility)
    assert result["synced"] is True
    assert result["category"] == "research_insight"
    assert result["content_lane"] == "research_insight"
    assert result["timing_state"] == "EXHAUSTED"
    assert "timing is exhausted" in result["instruction"]


def test_unsynced_handoff_does_not_override_frozen_category():
    frozen = {"symbol": "HOT", "category": "technical_setup"}
    preflight = {
        "selected_opportunity": {"symbol": "HOT", "category": "research_insight"},
        "editorial_authoritative_handoff": {
            "status": "BLOCKED",
            "symbol": "HOT",
            "timing_state": "EXHAUSTED",
        },
    }
    result = module.resolve_editorial_state(frozen, preflight, {})
    assert result["synced"] is False
    assert result["category"] == "technical_setup"
    assert result["content_lane"] == "technical_setup"
