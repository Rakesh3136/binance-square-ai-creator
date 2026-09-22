"""Revenue Content Director — verified monetization-aware experiment layer.

Builds bounded content priors from exact publication attribution, explicit
Square performance, prediction outcomes, and explicitly verified revenue.
It does not infer reader trades/revenue and never overrides market/evidence,
editorial, safety, visual, or production gates.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"

ATTRIBUTION = ANALYTICS / "publication_attribution.jsonl"
PERFORMANCE = ANALYTICS / "square_performance.jsonl"
OUTCOMES = ANALYTICS / "creator_7_2_outcomes.jsonl"
EXPERIMENT = ANALYTICS / "creator_7_4_experiment_plan.json"
FEEDBACK = LIVE / "creator_8_4_monetization_feedback.json"
REVENUE = ANALYTICS / "creator_8_0_monetization_engine.json"
OUT = LIVE / "revenue_content_director.json"
REPORT = INTEL / "revenue_content_director_report.json"

REVENUE_FLAGS = ("revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings")
REVENUE_VALUES = ("revenue_amount", "verified_revenue_amount", "earnings_amount", "verified_earnings_amount", "revenue", "earnings")
CONVERSION_KEYS = ("verified_conversions", "conversions_verified", "verified_conversion_count")
DIMENSIONS = ("category", "format", "hook_type", "visual_type", "story_lane", "signal_type", "experiment_id")


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
            pass
    return rows


def pid(row):
    raw = str(row.get("canonical_post_id") or row.get("post_id") or row.get("publication_id") or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw.lower()


def number(row, *keys):
    for key in keys:
        try:
            value = float(row.get(key))
            if math.isfinite(value):
                return value
        except (TypeError, ValueError):
            pass
    return 0.0


def verified_revenue(row):
    if not any(row.get(key) is True for key in REVENUE_FLAGS):
        return None
    for key in REVENUE_VALUES:
        try:
            value = float(row.get(key))
            if math.isfinite(value) and value >= 0:
                return value
        except (TypeError, ValueError):
            pass
    return None


def verified_conversions(row):
    return number(row, *CONVERSION_KEYS)


def engagement(row):
    views = number(row, "views", "view_count", "reach", "impressions")
    if views <= 0:
        return None, None
    score = (number(row, "likes", "like_count")
             + 2 * number(row, "replies", "reply_count", "comments")
             + 3 * number(row, "shares", "share_count")
             + 2 * number(row, "quotes")) / views * 1000
    return score, views


def merge_rows():
    attr = {pid(x): x for x in load_jsonl(ATTRIBUTION) if pid(x)}
    perf = load_jsonl(PERFORMANCE)
    outcomes = defaultdict(list)
    for x in load_jsonl(OUTCOMES):
        if pid(x):
            outcomes[pid(x)].append(x)

    merged = []
    for row in perf:
        post = pid(row)
        if not post or post not in attr:
            continue
        merged_row = {**attr[post], **row}
        # Metadata must originate from publication attribution; performance can
        # update numeric observations without replacing identity.
        merged_row["_post_id"] = post
        merged_row["_outcomes"] = outcomes.get(post, [])
        merged.append(merged_row)
    return merged


def group_key(row):
    return tuple(str(row.get(dim) or "unknown").strip().lower() for dim in DIMENSIONS)


def main():
    now = datetime.now(timezone.utc).isoformat()
    rows = merge_rows()
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    observations = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        revenues = [r for r in (verified_revenue(x) for x in items) if r is not None]
        conversions = [verified_conversions(x) for x in items if verified_conversions(x) > 0]
        engagement_scores = []
        views = []
        for item in items:
            score, view_count = engagement(item)
            if score is not None:
                engagement_scores.append(score)
                views.append(view_count)
        outcome_scores = []
        for item in items:
            for out in item.get("_outcomes", []):
                if out.get("outcome_score") is not None:
                    outcome_scores.append(number(out, "outcome_score"))

        observations.append({
            "dimensions": dict(zip(DIMENSIONS, key)),
            "samples": len(items),
            "verified_revenue_total_usdc": round(sum(revenues), 8) if revenues else None,
            "verified_revenue_observations": len(revenues),
            "verified_conversions_total": round(sum(conversions), 6) if conversions else None,
            "avg_engagement_score": round(sum(engagement_scores) / len(engagement_scores), 6) if engagement_scores else None,
            "avg_views": round(sum(views) / len(views), 2) if views else None,
            "avg_outcome_score": round(sum(outcome_scores) / len(outcome_scores), 6) if outcome_scores else None,
            "evidence": "VERIFIED_REVENUE_PLUS_OBSERVATION" if revenues else "OBSERVATIONAL_ONLY",
        })

    # Revenue is only an evidence flag/tie-breaker. No revenue-based causal
    # claim is made and small samples remain exploration candidates.
    def rank(x):
        rev = x["verified_revenue_total_usdc"] or 0.0
        conv = x["verified_conversions_total"] or 0.0
        eng = x["avg_engagement_score"] or 0.0
        outcome = x["avg_outcome_score"] or 0.0
        return min(rev, 1000) * 10 + min(conv, 100) * 0.5 + min(eng, 100) * 0.1 + min(outcome, 100) * 0.02

    observations.sort(key=rank, reverse=True)

    experiment = load_json(EXPERIMENT, {})
    active = experiment.get("current_experiment") if isinstance(experiment, dict) else {}
    feedback = load_json(FEEDBACK, {})
    revenue_report = load_json(REVENUE, {})

    monetized = [x for x in observations if (x["verified_revenue_total_usdc"] or 0) > 0]
    tested = observations[:8]

    director = {
        "version": "1.0",
        "generated_at": now,
        "status": "READY" if rows else "COLLECTING_DATA",
        "verified_data_policy": {
            "revenue_requires_explicit_verified_flag": True,
            "reader_trades_never_inferred": True,
            "revenue_never_inferred_from_views_or_engagement": True,
            "prediction_success_is_not_revenue": True,
            "missing_attribution_is_not_repaired_by_guessing": True,
        },
        "inputs": {
            "attributed_performance_rows": len(rows),
            "repeated_observations": len(observations),
            "monetized_observation_groups": len(monetized),
            "active_experiment_id": active.get("experiment_id") if isinstance(active, dict) else None,
            "feedback_version": feedback.get("version"),
            "revenue_engine_version": revenue_report.get("version"),
        },
        "content_priors": {
            "test_more": [
                {"dimensions": x["dimensions"], "reason": "observed evidence; keep as hypothesis, not guarantee"}
                for x in tested[:5]
            ],
            "explore_next": [
                {"dimension": active.get("primary_variable"), "treatment": active.get("treatment_value")}
            ] if active.get("primary_variable") else [],
            "avoid_repetition": [
                {"dimensions": x["dimensions"], "reason": "lower observed evidence; do not delete solely from this signal"}
                for x in observations[-3:]
            ],
        },
        "monetization_content_contract": {
            "preferred_lane": "signal_first_prediction_when_a_real_verified_setup_exists",
            "required_elements_for_trade_setup": ["symbol", "direction", "entry_or_trigger", "tp1", "tp2", "sl", "invalidation"],
            "cashtag_policy": "Use the exact asset cashtag/trading surface when supported by the publication contract; never fabricate a link or widget.",
            "cta_policy": "Invite readers to review the setup/evidence; never promise profit or pressure trading.",
            "visual_policy": "Use a validated Square-native trading setup visual when the lane requires one and ensure symbol consistency.",
            "story_forcing": False,
        },
        "experiment_policy": {
            "one_primary_editorial_variable": True,
            "reuse_existing_creator_7_4_experiment": True,
            "replicate_before_promoting": True,
            "minimum_repeated_samples": 3,
            "revenue_is_secondary_evidence": True,
            "quality_gates_remain_authoritative": True,
        },
        "next_cycle_instruction": "Use content_priors as bounded priors only after Signal-First selects a real opportunity. Do not manufacture a symbol, setup, revenue claim, or experiment completion.",
        "observations": observations[:100],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(director, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({
        "version": "1.0",
        "status": director["status"],
        "attributed_performance_rows": len(rows),
        "repeated_observations": len(observations),
        "monetized_observation_groups": len(monetized),
        "output": str(OUT.relative_to(ROOT)),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": director["status"],
        "version": "1.0",
        "attributed_performance_rows": len(rows),
        "repeated_observations": len(observations),
        "monetized_observation_groups": len(monetized),
        "active_experiment_id": active.get("experiment_id") if isinstance(active, dict) else None,
        "output": str(OUT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
