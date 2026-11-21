"""Quality-gated posting cadence recommendations; never grants publisher authorization."""
from __future__ import annotations
from typing import Any


def _num(metrics: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = float(metrics.get(key, default))
        if value != value or value in (float("inf"), float("-inf")):
            return default
        return value
    except (TypeError, ValueError):
        return default


def recommend_volume_stage(metrics: dict[str, Any]) -> dict[str, Any]:
    """Return the highest cadence tier supported by supplied evidence.

    Missing fields default conservatively. This function does not enable, call,
    or authorize publication.
    """
    if not isinstance(metrics, dict):
        metrics = {}
    drafts = int(_num(metrics, "reviewed_drafts"))
    quality = _num(metrics, "quality_pass_rate")
    critical = int(_num(metrics, "critical_errors", 0))
    duplicate = _num(metrics, "duplicate_rate", 1.0)
    chart_match = _num(metrics, "chart_match_rate")
    citations = _num(metrics, "source_citation_rate")
    healthy = int(_num(metrics, "consecutive_healthy_cycles"))
    pilot_days = int(_num(metrics, "verified_pilot_days"))
    pilot_posts = int(_num(metrics, "verified_pilot_posts"))
    pilot_quality = _num(metrics, "pilot_quality_pass_rate")
    complaints = int(_num(metrics, "substantiated_quality_complaints", 0))
    common = {
        "publisher_authorized": False,
        "revenue_used_for_decision": False,
        "evidence": {"reviewed_drafts": drafts, "quality_pass_rate": quality,
            "critical_errors": critical, "duplicate_rate": duplicate,
            "chart_match_rate": chart_match, "source_citation_rate": citations,
            "consecutive_healthy_cycles": healthy, "verified_pilot_days": pilot_days,
            "verified_pilot_posts": pilot_posts, "pilot_quality_pass_rate": pilot_quality,
            "substantiated_quality_complaints": complaints},
    }
    gates = [(drafts >= 20, "20_reviewed_drafts"), (quality >= .90, "quality_pass_rate_at_least_90_percent"),
        (critical == 0, "zero_critical_errors"), (duplicate <= .05, "duplicate_rate_at_most_5_percent"),
        (chart_match >= .98, "chart_match_rate_at_least_98_percent"),
        (citations >= .95, "source_citation_rate_at_least_95_percent"),
        (healthy >= 7, "seven_consecutive_healthy_cycles"),
        (complaints == 0, "zero_substantiated_quality_complaints")]
    missing = [name for ok, name in gates if not ok]
    if missing:
        return {**common, "stage": "DRAFT_ONLY", "recommended_posts_per_day": 0,
            "reason": "Draft evidence has not met every minimum quality and reliability gate.",
            "missing_requirements": missing}
    pilot_gates = [(pilot_days >= 7, "seven_verified_pilot_days"),
        (pilot_posts >= 7, "seven_verified_pilot_posts"),
        (pilot_quality >= .90, "pilot_quality_pass_rate_at_least_90_percent"),
        (complaints == 0, "zero_substantiated_quality_complaints"), (critical == 0, "zero_critical_errors")]
    pilot_missing = [name for ok, name in pilot_gates if not ok]
    if pilot_missing:
        return {**common, "stage": "ELIGIBLE_FOR_1_PER_DAY_PILOT", "recommended_posts_per_day": 1,
            "reason": "Draft quality gates passed; a low-volume live pilot may be considered separately, with explicit publisher authorization.",
            "missing_requirements": pilot_missing}
    scale_gates = [(pilot_days >= 14, "14_verified_pilot_days"), (pilot_posts >= 20, "20_verified_pilot_posts"),
        (pilot_quality >= .95, "pilot_quality_pass_rate_at_least_95_percent"),
        (quality >= .95, "draft_quality_pass_rate_at_least_95_percent")]
    scale_missing = [name for ok, name in scale_gates if not ok]
    if not scale_missing:
        return {**common, "stage": "ELIGIBLE_FOR_3_PER_DAY_CEILING", "recommended_posts_per_day": 3,
            "reason": "Quality gates and a verified 14-day pilot support a cautious higher cadence; publisher authorization remains separate.",
            "missing_requirements": []}
    return {**common, "stage": "ELIGIBLE_FOR_2_PER_DAY_PILOT", "recommended_posts_per_day": 2,
        "reason": "A verified 7-day pilot passed quality gates; expand only as a monitored pilot.",
        "missing_requirements": scale_missing}
