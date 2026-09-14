"""Creator 8.1 — Verified Revenue Attribution & Monetization Intelligence.

Builds a conservative monetization layer from explicit, attributable outcomes.
Money is never inferred from views, likes, followers, clicks, or engagement.
The engine separates verified revenue from unallocated revenue and descriptive
patterns from causal claims, then exposes bounded learning signals to the
portfolio/experiment layers without overriding editorial quality.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
INTEL = ROOT / "data" / "intelligence"
MEMORY = ANALYTICS / "strategy_memory.json"
OUTCOMES = ANALYTICS / "creator_7_2_outcomes.jsonl"
PLAN = ANALYTICS / "creator_8_0_monetization_engine.json"
REPORT = INTEL / "creator_8_0_report.json"

VERIFIED_REVENUE_KEYS = ("revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings")
REVENUE_VALUE_KEYS = ("revenue_amount", "verified_revenue_amount", "earnings_amount", "verified_earnings_amount", "revenue", "earnings")
CONVERSION_KEYS = ("verified_conversions", "conversions_verified", "verified_conversion_count")
FUNNEL = ("reach", "engagement", "follower_growth", "verified_conversion", "verified_revenue")
ATTRIBUTION_KEYS = ("experiment_id", "post_id", "canonical_post_id", "campaign_id")


def load_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def load_outcomes():
    rows = []
    if not OUTCOMES.exists():
        return rows
    for line in OUTCOMES.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except Exception:
            continue
    return rows


def num(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
            if math.isfinite(value):
                return value
    return 0.0


def verified_revenue(obj):
    if not any(obj.get(k) is True for k in VERIFIED_REVENUE_KEYS):
        return None
    value = num(obj, *REVENUE_VALUE_KEYS)
    return value if value >= 0 and math.isfinite(value) else None


def metric(row, *keys):
    return num(row, *keys)


def canonical_attribution(row):
    """Return the strongest explicit attribution identifier available."""
    for key in ("canonical_post_id", "post_id", "experiment_id", "campaign_id"):
        value = row.get(key)
        if value not in (None, "", False):
            return str(value), key
    return None, None


def label(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return "unknown"


def summarize_revenue(rows):
    buckets = defaultdict(lambda: {"revenue": 0.0, "records": 0, "conversions": 0})
    for row, rev in rows:
        category = label(row, "category")
        fmt = label(row, "format", "experiment_format")
        symbol = label(row, "symbol", "asset").upper()
        for dimension, value in (("category", category), ("format", fmt), ("symbol", symbol)):
            item = buckets[(dimension, value)]
            item["revenue"] += rev
            item["records"] += 1
            item["conversions"] += metric(row, *CONVERSION_KEYS)
    result = defaultdict(list)
    for (dimension, value), item in buckets.items():
        result[dimension].append({
            "value": value,
            "verified_revenue": round(item["revenue"], 8),
            "verified_revenue_records": item["records"],
            "verified_conversions": item["conversions"],
        })
    for dimension in result:
        result[dimension].sort(key=lambda x: (x["verified_revenue"], x["verified_revenue_records"]), reverse=True)
    return dict(result)


def main():
    now = datetime.now(timezone.utc).isoformat()
    outcomes = load_outcomes()

    reach = sum(metric(r, "views", "reach", "impressions") for r in outcomes)
    engagement = sum(metric(r, "likes") + metric(r, "comments") + metric(r, "shares") + metric(r, "quotes") for r in outcomes)
    follower_growth = sum(metric(r, "follower_growth", "followers_gained", "new_followers") for r in outcomes)
    verified_conversion = sum(metric(r, *CONVERSION_KEYS) for r in outcomes)

    revenue_rows = []
    for row in outcomes:
        rev = verified_revenue(row)
        if rev is not None:
            revenue_rows.append((row, rev))

    verified_total = sum(rev for _, rev in revenue_rows)
    allocated = []
    unallocated_total = 0.0
    attribution_quality = Counter()
    for row, rev in revenue_rows:
        attribution, attribution_type = canonical_attribution(row)
        if attribution:
            allocated.append({
                "attribution": attribution,
                "attribution_type": attribution_type,
                "revenue": round(rev, 8),
                "post_id": row.get("post_id"),
                "canonical_post_id": row.get("canonical_post_id"),
                "experiment_id": row.get("experiment_id"),
                "campaign_id": row.get("campaign_id"),
                "symbol": label(row, "symbol", "asset").upper(),
                "category": label(row, "category"),
            })
            attribution_quality[attribution_type] += 1
        else:
            unallocated_total += rev

    allocated_total = sum(item["revenue"] for item in allocated)
    conversion_rate = verified_conversion / max(reach, 1) * 100
    revenue_per_conversion = verified_total / verified_conversion if verified_conversion > 0 else None
    revenue_per_attributed_record = allocated_total / len(allocated) if allocated else None

    patterns = summarize_revenue(revenue_rows)
    status = "LEARNING_NO_VERIFIED_REVENUE" if not revenue_rows else "VERIFIED_REVENUE_OBSERVED"
    if allocated:
        status = "VERIFIED_REVENUE_ATTRIBUTED"

    strategy = {
        "version": "8.1",
        "status": status,
        "updated_at": now,
        "funnel": {
            "reach": round(reach, 4),
            "engagement": round(engagement, 4),
            "follower_growth": round(follower_growth, 4),
            "verified_conversion": round(verified_conversion, 4),
            "verified_revenue": round(verified_total, 8),
        },
        "funnel_rates": {
            "verified_conversion_per_reach_percent": round(conversion_rate, 8),
            "verified_revenue_per_conversion": round(revenue_per_conversion, 8) if revenue_per_conversion is not None else None,
            "verified_revenue_per_attributed_record": round(revenue_per_attributed_record, 8) if revenue_per_attributed_record is not None else None,
        },
        "revenue": {
            "verified_total": round(verified_total, 8),
            "verified_record_count": len(revenue_rows),
            "allocated_verified_revenue": round(allocated_total, 8),
            "allocated_record_count": len(allocated),
            "unallocated_verified_revenue": round(unallocated_total, 8),
            "attribution_coverage_percent": round(allocated_total / verified_total * 100, 4) if verified_total > 0 else 0.0,
            "revenue_is_inferred": False,
            "attribution_quality": dict(attribution_quality),
        },
        "descriptive_revenue_patterns": patterns,
        "monetization_learning": {
            "eligible_for_strategy_learning": bool(allocated),
            "strongest_attributed_dimension": None,
            "minimum_records_for_pattern_signal": 3,
            "causal_claims_allowed": False,
        },
        "optimization_policy": {
            "primary_goal": "improve useful reader journeys toward verified conversion while preserving content quality",
            "secondary_goals": ["quality reach", "substantive engagement", "follower growth"],
            "revenue_attribution_rule": "Only explicitly verified revenue is money; only explicit identifiers create attribution.",
            "causal_claims_allowed": False,
            "never_infer_revenue_from_views": True,
            "never_infer_revenue_from_followers": True,
            "never_force_weak_story_for_monetization": True,
            "never_optimize_for_clicks_without_quality_evidence": True,
            "never_use_revenue_to_override_safety_or_editorial_gates": True,
        },
        "next_actions": [
            "Use attributed revenue only as a bounded learning signal alongside Creator 7.3/7.4 and 7.5 outcomes.",
            "Prefer content that naturally creates qualified reader intent through useful evidence and accurate asset tagging.",
            "Keep verified revenue unallocated when the source cannot explicitly identify its post, experiment, or campaign.",
            "Require repeated attributable observations before changing portfolio strategy on monetization evidence.",
        ],
        "sample_size": len(outcomes),
    }

    # Select a descriptive pattern only when it has repeated attributable records.
    candidates = []
    for dimension, values in patterns.items():
        for item in values:
            if item["verified_revenue_records"] >= 3:
                candidates.append((item["verified_revenue"], dimension, item["value"]))
    if candidates:
        _, dimension, value = max(candidates)
        strategy["monetization_learning"]["strongest_attributed_dimension"] = {"dimension": dimension, "value": value, "evidence": "DESCRIPTIVE_REPEATED"}

    ANALYTICS.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(strategy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(strategy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    memory = load_json(MEMORY, {})
    if not isinstance(memory, dict):
        memory = {}
    memory["creator_8_0"] = strategy
    overlay = memory.setdefault("learning_overlay", {})
    overlay["revenue_engine"] = {
        "version": "8.1",
        "status": status,
        "verified_revenue": round(verified_total, 8),
        "allocated_verified_revenue": round(allocated_total, 8),
        "attribution_coverage_percent": strategy["revenue"]["attribution_coverage_percent"],
        "funnel": strategy["funnel"],
        "eligible_for_strategy_learning": bool(allocated),
        "revenue_inference_disabled": True,
        "updated_at": now,
    }
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "version": "8.1",
        "outcome_records": len(outcomes),
        "funnel": strategy["funnel"],
        "verified_revenue_records": len(revenue_rows),
        "allocated_verified_revenue": round(allocated_total, 8),
        "unallocated_verified_revenue": round(unallocated_total, 8),
        "attribution_coverage_percent": strategy["revenue"]["attribution_coverage_percent"],
        "outputs": [str(PLAN), str(REPORT), str(MEMORY)],
    }, indent=2))


if __name__ == "__main__":
    main()
