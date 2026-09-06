"""Creator 8.0 — Autonomous Revenue & Business Engine.

Turns verified creator outcomes into a monetization intelligence layer.
Revenue is NEVER inferred from views, likes, comments, shares, or followers.
Only explicitly verified revenue/earnings fields are treated as money.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
INTEL = ROOT / "data" / "intelligence"
MEMORY = ANALYTICS / "strategy_memory.json"
OUTCOMES = ANALYTICS / "creator_7_2_outcomes.jsonl"
PLAN = ANALYTICS / "creator_8_0_monetization_engine.json"
REPORT = INTEL / "creator_8_0_report.json"

VERIFIED_REVENUE_KEYS = (
    "revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings"
)
REVENUE_VALUE_KEYS = (
    "revenue_amount", "verified_revenue_amount", "earnings_amount", "verified_earnings_amount",
    "revenue", "earnings"
)
FUNNEL = ("reach", "engagement", "follower_growth", "verified_conversion", "verified_revenue")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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
            return float(value)
    return 0.0


def verified_revenue(obj):
    flag = any(obj.get(k) is True for k in VERIFIED_REVENUE_KEYS)
    if not flag:
        return None
    value = num(obj, *REVENUE_VALUE_KEYS)
    return value if math.isfinite(value) and value >= 0 else None


def metric(row, *keys):
    return num(row, *keys)


def main():
    now = datetime.now(timezone.utc).isoformat()
    outcomes = load_outcomes()

    funnel = {
        "reach": sum(metric(r, "views", "reach", "impressions") for r in outcomes),
        "engagement": sum(metric(r, "likes", "comments", "shares", "quotes") for r in outcomes),
        "follower_growth": sum(metric(r, "follower_growth", "followers_gained", "new_followers") for r in outcomes),
        "verified_conversion": sum(metric(r, "verified_conversions", "conversions_verified", "verified_conversion_count") for r in outcomes),
    }
    revenue_rows = []
    for row in outcomes:
        rev = verified_revenue(row)
        if rev is not None:
            revenue_rows.append((row, rev))
    funnel["verified_revenue"] = sum(v for _, v in revenue_rows)

    # Conversion/revenue attribution is only considered allocated when the source
    # explicitly identifies the post/experiment/campaign. Otherwise it remains unallocated.
    allocated = []
    unallocated_revenue = 0.0
    for row, rev in revenue_rows:
        attribution = row.get("experiment_id") or row.get("post_id") or row.get("campaign_id")
        if attribution:
            allocated.append({
                "attribution": str(attribution),
                "revenue": rev,
                "experiment_id": row.get("experiment_id"),
                "post_id": row.get("post_id"),
                "campaign_id": row.get("campaign_id"),
            })
        else:
            unallocated_revenue += rev

    # Revenue-aware patterns are descriptive only. No causal claim is made.
    by_format = defaultdict(list)
    by_category = defaultdict(list)
    for row, rev in revenue_rows:
        for key, bucket in (("format", by_format), ("category", by_category)):
            value = row.get(key) or row.get(f"experiment_{key}") or "unknown"
            bucket[str(value)].append(rev)

    def summarize(bucket):
        return [
            {"value": k, "verified_revenue": round(sum(v), 8), "verified_revenue_records": len(v)}
            for k, v in sorted(bucket.items(), key=lambda x: sum(x[1]), reverse=True)
        ]

    total_rows = len(outcomes)
    status = "LEARNING_NO_VERIFIED_REVENUE"
    if revenue_rows:
        status = "VERIFIED_REVENUE_OBSERVED"

    strategy = {
        "status": status,
        "updated_at": now,
        "funnel": funnel,
        "revenue": {
            "verified_total": funnel["verified_revenue"],
            "verified_record_count": len(revenue_rows),
            "allocated_verified_revenue": round(sum(x["revenue"] for x in allocated), 8),
            "unallocated_verified_revenue": round(unallocated_revenue, 8),
            "revenue_is_inferred": False,
        },
        "descriptive_revenue_patterns": {
            "by_format": summarize(by_format),
            "by_category": summarize(by_category),
        },
        "optimization_policy": {
            "primary_goal": "move users through the funnel toward verified conversion and verified revenue",
            "secondary_goals": ["quality reach", "substantive engagement", "follower growth"],
            "revenue_attribution_rule": "Only explicitly verified revenue is money; only explicit attribution is allocated.",
            "causal_claims_allowed": False,
            "never_infer_revenue_from_views": True,
            "never_infer_revenue_from_followers": True,
            "never_force_weak_story_for_monetization": True,
        },
        "next_actions": [
            "Continue testing high-quality content formats with measurable funnel outcomes.",
            "Prefer experiments that can expose verified conversion signals when such signals exist.",
            "Keep revenue unallocated when the source does not explicitly link it to a post, experiment, or campaign.",
        ],
        "sample_size": total_rows,
    }

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
        "status": status,
        "verified_revenue": funnel["verified_revenue"],
        "verified_revenue_records": len(revenue_rows),
        "funnel": funnel,
        "updated_at": now,
        "revenue_inference_disabled": True,
    }
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "outcome_records": total_rows,
        "funnel": funnel,
        "verified_revenue_records": len(revenue_rows),
        "allocated_verified_revenue": strategy["revenue"]["allocated_verified_revenue"],
        "unallocated_verified_revenue": strategy["revenue"]["unallocated_verified_revenue"],
        "outputs": [str(PLAN), str(REPORT), str(MEMORY)],
    }, indent=2))


if __name__ == "__main__":
    main()
