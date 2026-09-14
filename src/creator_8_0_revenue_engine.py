"""Creator 8.2 — Revenue Attribution Feedback Loop.

Connects explicitly verified revenue back to the post, asset, category,
format, hook, thesis, signal, experiment and portfolio decision that produced
it when those identifiers are actually present. This is descriptive learning,
not proof of causality. Missing attribution stays missing rather than being
invented.
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

REVENUE_FLAGS = ("revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings")
REVENUE_VALUES = ("revenue_amount", "verified_revenue_amount", "earnings_amount", "verified_earnings_amount", "revenue", "earnings")
CONVERSION_KEYS = ("verified_conversions", "conversions_verified", "verified_conversion_count")
ATTRIBUTION_KEYS = ("canonical_post_id", "post_id", "experiment_id", "campaign_id")
LEARNING_DIMS = (
    "symbol", "category", "format", "experiment_format", "hook_type", "thesis_type",
    "signal_type", "story_lane", "market_regime", "visual_type", "experiment_id",
)


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
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
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


def revenue(row):
    if not any(row.get(k) is True for k in REVENUE_FLAGS):
        return None
    value = num(row, *REVENUE_VALUES)
    return value if math.isfinite(value) and value >= 0 else None


def label(row, *keys):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", False):
            return str(value)
    return "unknown"


def attribution(row):
    for key in ATTRIBUTION_KEYS:
        value = row.get(key)
        if value not in (None, "", False):
            return str(value), key
    return None, None


def metric(row, *keys):
    return num(row, *keys)


def outcome_score(row):
    if row.get("outcome_score") is not None:
        return num(row, "outcome_score")
    m = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
    views = num(m, "views", "reach", "impressions")
    if views <= 0:
        return 0.0
    return (num(m, "likes") + 2 * num(m, "comments") + 3 * num(m, "shares") + 2 * num(m, "quotes")) / views * 1000


def main():
    now = datetime.now(timezone.utc).isoformat()
    rows = load_outcomes()
    verified = [(row, revenue(row)) for row in rows]
    verified = [(row, rev) for row, rev in verified if rev is not None]

    attributed = []
    unallocated = 0.0
    for row, rev in verified:
        ident, ident_type = attribution(row)
        if ident:
            attributed.append((row, rev, ident, ident_type))
        else:
            unallocated += rev

    # Attribute only from fields explicitly carried by the outcome record.
    # This produces a causal-style lineage graph without inventing missing links.
    lineage = []
    for row, rev, ident, ident_type in attributed:
        lineage.append({
            "attribution": ident,
            "attribution_type": ident_type,
            "verified_revenue": round(rev, 8),
            "verified_conversions": metric(row, *CONVERSION_KEYS),
            "outcome_score": round(outcome_score(row), 6),
            "symbol": label(row, "symbol", "asset").upper(),
            "category": label(row, "category"),
            "format": label(row, "format", "experiment_format"),
            "hook_type": label(row, "hook_type"),
            "thesis_type": label(row, "thesis_type"),
            "signal_type": label(row, "signal_type"),
            "story_lane": label(row, "story_lane"),
            "market_regime": label(row, "market_regime"),
            "visual_type": label(row, "visual_type"),
            "experiment_id": row.get("experiment_id"),
            "portfolio_bucket": row.get("portfolio_bucket") or row.get("growth_bucket"),
            "source_timestamp": row.get("timestamp") or row.get("created_at") or row.get("published_at"),
        })

    # Repeated attributable observations are descriptive signals only.
    patterns = defaultdict(lambda: {"records": 0, "revenue": 0.0, "conversions": 0.0, "scores": []})
    for item in lineage:
        for dim in LEARNING_DIMS:
            value = item.get(dim)
            if value in (None, "", "unknown"):
                continue
            bucket = patterns[(dim, str(value))]
            bucket["records"] += 1
            bucket["revenue"] += item["verified_revenue"]
            bucket["conversions"] += item["verified_conversions"]
            bucket["scores"].append(item["outcome_score"])

    repeated = []
    for (dim, value), item in patterns.items():
        if item["records"] < 3:
            continue
        scores = sorted(item["scores"])
        repeated.append({
            "dimension": dim,
            "value": value,
            "records": item["records"],
            "verified_revenue": round(item["revenue"], 8),
            "verified_conversions": round(item["conversions"], 6),
            "median_outcome_score": round(scores[len(scores) // 2], 6),
            "evidence": "DESCRIPTIVE_REPEATED",
        })
    repeated.sort(key=lambda x: (x["verified_revenue"], x["records"]), reverse=True)

    total_revenue = sum(rev for _, rev in verified)
    allocated_revenue = sum(item["verified_revenue"] for item in lineage)
    conversions = sum(metric(row, *CONVERSION_KEYS) for row, _ in verified)
    reach = sum(metric(row, "views", "reach", "impressions") for row in rows)

    strategy = {
        "version": "8.2",
        "status": "VERIFIED_REVENUE_ATTRIBUTED" if lineage else ("VERIFIED_REVENUE_OBSERVED" if verified else "LEARNING_NO_VERIFIED_REVENUE"),
        "updated_at": now,
        "lineage": {
            "attributed_record_count": len(lineage),
            "unallocated_verified_record_count": len(verified) - len(lineage),
            "verified_revenue": round(total_revenue, 8),
            "allocated_verified_revenue": round(allocated_revenue, 8),
            "unallocated_verified_revenue": round(unallocated, 8),
            "attribution_coverage_percent": round(allocated_revenue / total_revenue * 100, 4) if total_revenue else 0.0,
            "identifier_priority": list(ATTRIBUTION_KEYS),
            "missing_links_are_not_inferred": True,
        },
        "funnel": {
            "reach": round(reach, 4),
            "verified_conversion": round(conversions, 4),
            "verified_revenue": round(total_revenue, 8),
            "verified_conversion_per_reach_percent": round(conversions / max(reach, 1) * 100, 8),
            "revenue_per_verified_conversion": round(total_revenue / conversions, 8) if conversions else None,
        },
        "revenue_lineage": lineage[-500:],
        "repeated_monetization_signals": repeated[:100],
        "learning_policy": {
            "use_for_strategy": bool(repeated),
            "minimum_repeated_records": 3,
            "causal_claims_allowed": False,
            "promotion_requires_independent_experiment": True,
            "revenue_alone_cannot_override_editorial_quality": True,
            "revenue_alone_cannot_override_safety": True,
            "never_optimize_for_clicks_without_quality_evidence": True,
            "never_force_weak_story_for_monetization": True,
        },
        "next_actions": [
            "Feed repeated attributable signals into Creator 7.4 experiment selection as hypotheses, not guarantees.",
            "Feed stable portfolio-level patterns into Creator 7.5 only after repeated attributable evidence.",
            "Preserve exact post/experiment attribution so future outcomes can explain why revenue occurred.",
            "Keep unallocated verified revenue visible but excluded from attribution-based strategy learning.",
        ],
        "sample_size": len(rows),
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
        "version": "8.2",
        "status": strategy["status"],
        "allocated_verified_revenue": strategy["lineage"]["allocated_verified_revenue"],
        "attribution_coverage_percent": strategy["lineage"]["attribution_coverage_percent"],
        "repeated_signal_count": len(repeated),
        "learning_policy": strategy["learning_policy"],
        "updated_at": now,
        "revenue_inference_disabled": True,
    }
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": strategy["status"],
        "version": "8.2",
        "outcome_records": len(rows),
        "verified_revenue_records": len(verified),
        "attributed_records": len(lineage),
        "repeated_signals": len(repeated),
        "allocated_verified_revenue": round(allocated_revenue, 8),
        "unallocated_verified_revenue": round(unallocated, 8),
        "attribution_coverage_percent": strategy["lineage"]["attribution_coverage_percent"],
        "outputs": [str(PLAN), str(REPORT), str(MEMORY)],
    }, indent=2))


if __name__ == "__main__":
    main()
