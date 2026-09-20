"""Creator 9.0 — verified monetization attribution and outcome learning.

Builds a durable funnel from verified Square publications to exact post IDs,
public performance observations, prediction outcomes, and explicitly verified
revenue/conversions. Missing attribution stays missing. Revenue is never
inferred from views, clicks, likes, or prediction success.
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
PREDICTIONS = ANALYTICS / "prediction_outcomes.jsonl"
ATTRIBUTION = ANALYTICS / "publication_attribution.jsonl"
PERFORMANCE = ANALYTICS / "square_performance.jsonl"
PLAN = ANALYTICS / "creator_8_0_monetization_engine.json"
REPORT = INTEL / "creator_8_0_report.json"
REPORT_9 = INTEL / "creator_9_0_monetization_report.json"

REVENUE_FLAGS = (
    "revenue_verified",
    "verified_revenue",
    "earnings_verified",
    "verified_earnings",
)
REVENUE_VALUES = (
    "revenue_amount",
    "verified_revenue_amount",
    "earnings_amount",
    "verified_earnings_amount",
    "revenue",
    "earnings",
)
CONVERSION_KEYS = (
    "verified_conversions",
    "conversions_verified",
    "verified_conversion_count",
)
ATTRIBUTION_KEYS = (
    "canonical_post_id",
    "post_id",
    "experiment_id",
    "campaign_id",
)
LEARNING_DIMS = (
    "symbol",
    "category",
    "format",
    "experiment_format",
    "hook_type",
    "thesis_type",
    "signal_type",
    "story_lane",
    "market_regime",
    "visual_type",
    "experiment_id",
)


def load_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            continue
    return rows


def normalize_post_id(value):
    raw = str(value or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw.lower()


def num(obj, *keys):
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
            if math.isfinite(value):
                return value
    return 0.0


def revenue(row):
    # Revenue must be explicitly marked verified by an upstream source.
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


def outcome_score(row):
    if row.get("outcome_score") is not None:
        return num(row, "outcome_score")
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
    views = num(metrics, "views", "reach", "impressions")
    if views <= 0:
        return 0.0
    return (
        num(metrics, "likes")
        + 2 * num(metrics, "comments")
        + 3 * num(metrics, "shares")
        + 2 * num(metrics, "quotes")
    ) / views * 1000


def index_by_post(rows):
    index = defaultdict(list)
    for row in rows:
        pid = normalize_post_id(
            row.get("canonical_post_id")
            or row.get("post_id")
            or row.get("publication_id")
        )
        if pid:
            index[pid].append(row)
    return index


def merge_publication_metadata(row, attribution_rows):
    merged = dict(row)
    pid = normalize_post_id(
        row.get("canonical_post_id") or row.get("post_id")
    )
    matches = attribution_rows.get(pid, [])
    source = matches[-1] if matches else None
    if source:
        for key in (
            "symbol",
            "category",
            "direction",
            "experiment_id",
            "reference_price",
            "trigger",
            "invalidation",
            "targets",
            "cashtag",
            "visual_attached",
            "visual_url",
            "published_at",
        ):
            if merged.get(key) in (None, "", [], False):
                merged[key] = source.get(key)
        merged["_attribution_source"] = "publication_attribution"
    return merged


def main():
    now = datetime.now(timezone.utc).isoformat()

    outcome_rows = load_jsonl(OUTCOMES)
    prediction_rows = load_jsonl(PREDICTIONS)
    attribution_rows = load_jsonl(ATTRIBUTION)
    performance_rows = load_jsonl(PERFORMANCE)

    attribution_index = index_by_post(attribution_rows)
    performance_index = index_by_post(performance_rows)
    prediction_index = index_by_post(prediction_rows)

    # Attach publication lineage to older/newer outcome records by exact post ID.
    enriched_outcomes = [
        merge_publication_metadata(row, attribution_index)
        for row in outcome_rows
    ]

    verified = []
    unallocated = 0.0
    lineage = []

    for row in enriched_outcomes:
        rev = revenue(row)
        if rev is None:
            continue
        ident, ident_type = attribution(row)
        if ident:
            pid = normalize_post_id(
                row.get("canonical_post_id") or row.get("post_id")
            )
            lineage.append(
                {
                    "attribution": ident,
                    "attribution_type": ident_type,
                    "canonical_post_id": pid or None,
                    "verified_revenue": round(rev, 8),
                    "verified_conversions": num(row, *CONVERSION_KEYS),
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
                    "cashtag": row.get("cashtag"),
                    "source_timestamp": (
                        row.get("timestamp")
                        or row.get("created_at")
                        or row.get("published_at")
                    ),
                    "source": "explicitly_verified_revenue_field",
                }
            )
            verified.append((row, rev))
        else:
            unallocated += rev
            verified.append((row, rev))

    # Build a post-level funnel without turning engagement into money.
    funnel = []
    verified_revenue_by_post = defaultdict(float)
    verified_conversions_by_post = defaultdict(float)
    for row, rev in verified:
        pid = normalize_post_id(
            row.get("canonical_post_id") or row.get("post_id")
        )
        if pid:
            verified_revenue_by_post[pid] += rev
            verified_conversions_by_post[pid] += num(row, *CONVERSION_KEYS)

    for attr in attribution_rows:
        pid = normalize_post_id(
            attr.get("canonical_post_id") or attr.get("post_id")
        )
        if not pid:
            continue

        perf = performance_index.get(pid, [])
        latest_perf = perf[-1] if perf else {}
        perf_metrics = (
            latest_perf.get("metrics")
            if isinstance(latest_perf.get("metrics"), dict)
            else {}
        )

        pred = prediction_index.get(pid, [])
        latest_prediction = pred[-1] if pred else {}

        funnel.append(
            {
                "canonical_post_id": pid,
                "published_at": attr.get("published_at"),
                "symbol": str(attr.get("symbol") or "").upper(),
                "category": attr.get("category"),
                "direction": attr.get("direction"),
                "experiment_id": attr.get("experiment_id"),
                "cashtag": attr.get("cashtag"),
                "has_primary_cashtag": attr.get("has_primary_cashtag"),
                "verified_widget": attr.get("verified_widget"),
                "visual_attached": attr.get("visual_attached"),
                "performance": {
                    "matched": bool(latest_perf),
                    "views": num(perf_metrics, "views"),
                    "likes": num(perf_metrics, "likes"),
                    "comments": num(perf_metrics, "comments"),
                    "shares": num(perf_metrics, "shares"),
                    "quotes": num(perf_metrics, "quotes"),
                },
                "prediction": {
                    "matched": bool(latest_prediction),
                    "outcome": latest_prediction.get("outcome"),
                    "evaluated_at": latest_prediction.get("evaluated_at"),
                },
                "verified_activity": {
                    "qualified_trade_count": (
                        round(verified_conversions_by_post[pid], 8)
                        if pid in verified_conversions_by_post
                        else None
                    ),
                    "revenue_verified": pid in verified_revenue_by_post,
                    "reward_amount_usdc": (
                        round(verified_revenue_by_post[pid], 8)
                        if pid in verified_revenue_by_post
                        else None
                    ),
                    "status": (
                        "VERIFIED_REVENUE_OBSERVED"
                        if pid in verified_revenue_by_post
                        else "AWAITING_EXPLICIT_VERIFIED_REVENUE"
                    ),
                },
                "revenue_never_inferred_from_engagement": True,
            }
        )

    patterns = defaultdict(
        lambda: {"records": 0, "revenue": 0.0, "conversions": 0.0, "scores": []}
    )
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
        repeated.append(
            {
                "dimension": dim,
                "value": value,
                "records": item["records"],
                "verified_revenue": round(item["revenue"], 8),
                "verified_conversions": round(item["conversions"], 6),
                "median_outcome_score": round(
                    scores[len(scores) // 2], 6
                ),
                "evidence": "DESCRIPTIVE_REPEATED",
            }
        )
    repeated.sort(
        key=lambda x: (x["verified_revenue"], x["records"]), reverse=True
    )

    total_revenue = sum(rev for _, rev in verified)
    allocated_revenue = sum(item["verified_revenue"] for item in lineage)
    conversions = sum(
        num(row, *CONVERSION_KEYS) for row, _ in verified
    )
    matched_performance = sum(
        1 for item in funnel if item["performance"]["matched"]
    )
    total_views = sum(
        item["performance"]["views"] for item in funnel
    )
    terminal_predictions = sum(
        1
        for item in funnel
        if item["prediction"]["outcome"]
        in {"WIN", "LOSS", "INVALIDATED"}
    )

    strategy = {
        "version": "9.0",
        "status": (
            "VERIFIED_REVENUE_ATTRIBUTED"
            if lineage
            else (
                "VERIFIED_REVENUE_OBSERVED"
                if verified
                else "LEARNING_NO_VERIFIED_REVENUE"
            )
        ),
        "updated_at": now,
        "lineage": {
            "publication_attribution_records": len(attribution_rows),
            "attributed_revenue_records": len(lineage),
            "verified_revenue_records": len(verified),
            "unallocated_verified_revenue_records": len(verified) - len(lineage),
            "verified_revenue": round(total_revenue, 8),
            "allocated_verified_revenue": round(allocated_revenue, 8),
            "unallocated_verified_revenue": round(unallocated, 8),
            "attribution_coverage_percent": (
                round(allocated_revenue / total_revenue * 100, 4)
                if total_revenue
                else 0.0
            ),
            "identifier_priority": list(ATTRIBUTION_KEYS),
            "missing_links_are_not_inferred": True,
        },
        "funnel": {
            "verified_publications_tracked": len(funnel),
            "performance_matched_publications": matched_performance,
            "prediction_outcome_matched_publications": sum(
                1 for item in funnel if item["prediction"]["matched"]
            ),
            "terminal_prediction_outcomes": terminal_predictions,
            "observed_views": round(total_views, 4),
            "verified_conversions": round(conversions, 4),
            "verified_revenue": round(total_revenue, 8),
            "verified_conversion_per_view_percent": (
                round(conversions / max(total_views, 1) * 100, 8)
            ),
            "revenue_per_verified_conversion": (
                round(total_revenue / conversions, 8)
                if conversions
                else None
            ),
        },
        "publication_funnel": funnel[-500:],
        "revenue_lineage": lineage[-500:],
        "repeated_monetization_signals": repeated[:100],
        "learning_policy": {
            "use_for_strategy": bool(repeated),
            "minimum_repeated_records": 3,
            "causal_claims_allowed": False,
            "promotion_requires_independent_experiment": True,
            "revenue_alone_cannot_override_editorial_quality": True,
            "revenue_alone_cannot_override_safety": True,
            "engagement_is_not_revenue": True,
            "prediction_success_is_not_revenue": True,
            "never_optimize_for_clicks_without_quality_evidence": True,
            "never_force_weak_story_for_monetization": True,
            "never_infer_reader_trades": True,
        },
        "next_actions": [
            "Match future Square performance records by exact canonical post ID.",
            "Ingest only explicitly verified conversion/revenue fields into monetization learning.",
            "Feed repeated attributable patterns into experiment selection as hypotheses, not guarantees.",
            "Keep unallocated verified revenue visible but excluded from attribution-based strategy learning.",
        ],
        "sample_size": len(attribution_rows),
    }

    ANALYTICS.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(
        json.dumps(strategy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    REPORT.write_text(
        json.dumps(strategy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    REPORT_9.write_text(
        json.dumps(strategy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    memory = load_json(MEMORY, {})
    if not isinstance(memory, dict):
        memory = {}
    memory["creator_8_0"] = strategy
    overlay = memory.setdefault("learning_overlay", {})
    overlay["revenue_engine"] = {
        "version": "9.0",
        "status": strategy["status"],
        "allocated_verified_revenue": strategy["lineage"]["allocated_verified_revenue"],
        "attribution_coverage_percent": strategy["lineage"]["attribution_coverage_percent"],
        "repeated_signal_count": len(repeated),
        "tracked_publications": len(funnel),
        "performance_matched_publications": matched_performance,
        "learning_policy": strategy["learning_policy"],
        "updated_at": now,
        "revenue_inference_disabled": True,
    }
    MEMORY.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": strategy["status"],
                "version": "9.0",
                "publication_attribution_records": len(attribution_rows),
                "outcome_records": len(outcome_rows),
                "performance_records": len(performance_rows),
                "prediction_records": len(prediction_rows),
                "verified_revenue_records": len(verified),
                "attributed_revenue_records": len(lineage),
                "tracked_publications": len(funnel),
                "performance_matched": matched_performance,
                "terminal_predictions": terminal_predictions,
                "repeated_signals": len(repeated),
                "allocated_verified_revenue": round(allocated_revenue, 8),
                "unallocated_verified_revenue": round(unallocated, 8),
                "attribution_coverage_percent": strategy["lineage"][
                    "attribution_coverage_percent"
                ],
                "outputs": [
                    str(PLAN),
                    str(REPORT),
                    str(REPORT_9),
                    str(MEMORY),
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
