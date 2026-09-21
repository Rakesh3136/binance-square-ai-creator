"""Creator 8.4 — verified monetization feedback + experiment loop.

Combines observed Square engagement, prediction outcomes, and explicitly
verified monetization into a bounded feedback board. It recommends what to
TEST next; it never invents revenue, treats views as revenue, or overrides
signal/editorial/safety gates.
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
PERFORMANCE = ANALYTICS / "square_performance.jsonl"
ATTRIBUTION = ANALYTICS / "publication_attribution.jsonl"
OUTCOMES = ANALYTICS / "creator_7_2_outcomes.jsonl"
MONETIZATION = ANALYTICS / "creator_8_0_monetization_engine.json"
DECISION = ANALYTICS / "creator_8_3_monetization_decision.json"
AUDIENCE = LIVE / "creator_22_0_audience_board.json"
PLAN = ANALYTICS / "creator_7_4_experiment_plan.json"
MEMORY = ANALYTICS / "strategy_memory.json"
OUT = LIVE / "creator_8_4_monetization_feedback.json"
REPORT = INTEL / "creator_8_4_report.json"

MIN_SAMPLES = 3


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


def num(row, *keys):
    for key in keys:
        try:
            value = float(row.get(key))
            if math.isfinite(value):
                return value
        except (TypeError, ValueError):
            pass
    return 0.0


def pid(row):
    raw = str(row.get("canonical_post_id") or row.get("post_id") or row.get("publication_id") or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw.lower()


def dimension_key(row):
    return (
        str(row.get("format") or row.get("experiment_format") or "unknown"),
        str(row.get("hook_type") or "unknown"),
        str(row.get("category") or "unknown"),
        str(row.get("visual_type") or "unknown"),
        str(row.get("experiment_id") or "unknown"),
    )


def engagement_score(row):
    views = num(row, "views", "view_count", "reach", "impressions")
    if views <= 0:
        return None
    return (num(row, "likes", "like_count") + 2 * num(row, "replies", "reply_count", "comments") + 3 * num(row, "shares", "share_count") + 2 * num(row, "quotes")) / views * 1000


def verified_revenue(row):
    flags = ("revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings")
    if not any(row.get(k) is True for k in flags):
        return None
    for key in ("revenue_amount", "verified_revenue_amount", "earnings_amount", "verified_earnings_amount", "revenue", "earnings"):
        try:
            value = float(row.get(key))
            if math.isfinite(value) and value >= 0:
                return value
        except (TypeError, ValueError):
            pass
    return None


def main():
    now = datetime.now(timezone.utc).isoformat()
    performance = load_jsonl(PERFORMANCE)
    attribution = load_jsonl(ATTRIBUTION)
    outcomes = load_jsonl(OUTCOMES)
    audience = load_json(AUDIENCE, {})
    monetization = load_json(MONETIZATION, {})
    decision = load_json(DECISION, {})
    plan = load_json(PLAN, {})

    attr = {pid(r): r for r in attribution if pid(r)}
    outcome_by_post = defaultdict(list)
    for row in outcomes:
        if pid(row):
            outcome_by_post[pid(row)].append(row)

    groups = defaultdict(lambda: {"samples": 0, "engagement": [], "views": [], "followers": [], "verified_revenue": [], "verified_conversions": [], "outcome_scores": []})
    matched_posts = 0
    verified_revenue_rows = 0

    for row in performance:
        post = pid(row)
        if not post:
            continue
        metadata = dict(attr.get(post, {}))
        merged = {**metadata, **row}
        # Only use explicit attribution fields; do not infer identity from text.
        if not any(merged.get(k) for k in ("format", "experiment_format", "hook_type", "category", "visual_type", "experiment_id")):
            continue
        matched_posts += 1
        key = dimension_key(merged)
        g = groups[key]
        g["samples"] += 1
        views = num(merged, "views", "view_count", "reach", "impressions")
        if views > 0:
            g["views"].append(views)
        score = engagement_score(merged)
        if score is not None:
            g["engagement"].append(score)
        followers = num(merged, "followers_gained", "follower_growth")
        if followers:
            g["followers"].append(followers)
        rev = verified_revenue(merged)
        if rev is not None:
            verified_revenue_rows += 1
            g["verified_revenue"].append(rev)
        conv = num(merged, "verified_conversions", "conversions_verified", "verified_conversion_count")
        if conv:
            g["verified_conversions"].append(conv)
        for out in outcome_by_post.get(post, []):
            if out.get("outcome_score") is not None:
                g["outcome_scores"].append(num(out, "outcome_score"))

    observations = []
    for key, g in groups.items():
        if g["samples"] < MIN_SAMPLES:
            continue
        observations.append({
            "dimensions": {"format": key[0], "hook_type": key[1], "category": key[2], "visual_type": key[3], "experiment_id": key[4]},
            "samples": g["samples"],
            "avg_engagement_score": round(sum(g["engagement"]) / len(g["engagement"]), 6) if g["engagement"] else None,
            "avg_views": round(sum(g["views"]) / len(g["views"]), 2) if g["views"] else None,
            "avg_followers_gained": round(sum(g["followers"]) / len(g["followers"]), 4) if g["followers"] else None,
            "verified_revenue_total": round(sum(g["verified_revenue"]), 8) if g["verified_revenue"] else None,
            "verified_conversions_total": round(sum(g["verified_conversions"]), 4) if g["verified_conversions"] else None,
            "avg_outcome_score": round(sum(g["outcome_scores"]) / len(g["outcome_scores"]), 6) if g["outcome_scores"] else None,
            "evidence": "REPEATED_OBSERVATIONAL",
        })

    # Revenue is a tie-breaker only when it is explicitly verified. Engagement
    # and prediction outcomes remain separate signals; no causal claim is made.
    def rank(row):
        engagement = row["avg_engagement_score"] or 0.0
        followers = row["avg_followers_gained"] or 0.0
        outcome = row["avg_outcome_score"] or 0.0
        revenue = row["verified_revenue_total"] or 0.0
        conversions = row["verified_conversions_total"] or 0.0
        return engagement + min(followers, 100) * 0.25 + min(outcome, 100) * 0.05 + min(revenue, 100) * 0.02 + min(conversions, 20) * 0.5

    observations.sort(key=rank, reverse=True)
    recommendations = []
    for row in observations[:5]:
        recommendations.append({
            "action": "INCREASE_TESTING",
            "dimensions": row["dimensions"],
            "reason": "repeated_observed_engagement_with_optional_verified_monetization_evidence",
            "evidence": {k: row[k] for k in ("samples", "avg_engagement_score", "avg_views", "avg_followers_gained", "verified_revenue_total", "verified_conversions_total")},
            "policy": "test_more_when_naturally_eligible; never force the story or claim causality",
        })
    for row in observations[-3:]:
        recommendations.append({
            "action": "REDUCE_REPETITION",
            "dimensions": row["dimensions"],
            "reason": "repeated_observed_weak_engagement_relative_to_other_observations",
            "policy": "reduce repetition; do not delete the dimension solely from observational data",
        })

    active = plan.get("current_experiment") if isinstance(plan, dict) else None
    feedback = {
        "version": "8.4",
        "generated_at": now,
        "status": "OK",
        "matched_publications": matched_posts,
        "repeated_observations": len(observations),
        "verified_revenue_rows": verified_revenue_rows,
        "active_experiment_id": active.get("experiment_id") if isinstance(active, dict) else None,
        "upstream_monetization_decision": decision.get("decision"),
        "audience_samples": audience.get("samples", 0),
        "observations": observations[:20],
        "recommendations": recommendations,
        "selection_policy": {
            "objective": "maximize_learning_about_quality_engagement_and_legitimate_monetization",
            "minimum_repeated_samples": MIN_SAMPLES,
            "verified_revenue_is_secondary_signal": True,
            "views_are_not_revenue": True,
            "no_revenue_inference": True,
            "no_causal_claims": True,
            "no_story_forcing": True,
            "no_engagement_manipulation": True,
            "editorial_and_prediction_gates_remain_authoritative": True,
        },
        "next_cycle": "Use recommendations only as bounded experiment/format priors; keep Signal-First selection, factual integrity, visual validation and production gates authoritative.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(feedback, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({"version": "8.4", "status": "OK", "matched_publications": matched_posts, "repeated_observations": len(observations), "verified_revenue_rows": verified_revenue_rows}, indent=2) + "\n", encoding="utf-8")

    memory = load_json(MEMORY, {})
    overlay = memory.get("learning_overlay") if isinstance(memory.get("learning_overlay"), dict) else {}
    overlay["monetization_feedback_8_4"] = {
        "version": "8.4",
        "updated_at": now,
        "repeated_observations": len(observations),
        "recommendations": recommendations[:5],
        "verified_revenue_rows": verified_revenue_rows,
        "revenue_inference_disabled": True,
        "story_forcing_disabled": True,
    }
    memory["learning_overlay"] = overlay
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"status": "OK", "version": "8.4", "matched_publications": matched_posts, "repeated_observations": len(observations), "verified_revenue_rows": verified_revenue_rows, "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
