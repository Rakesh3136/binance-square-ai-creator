"""Creator-period reward learning for Binance Square Write-to-Earn.

The leaderboard reward is a creator-period outcome. This module studies all collected
posts in the matching 7-day and 14-day windows as a cohort; it NEVER divides or assigns
the creator's reward to individual posts. A period can inform hypotheses, not prove which
post caused earnings.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD_PATH = ROOT / "data/intelligence/wte_leaderboard_observations.json"
POSTS_INPUT_PATH = ROOT / "data/intelligence/research/creator_period_posts.json"
OUTPUT_PATH = ROOT / "data/intelligence/creator_period_learning.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _norm(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _creator_match(a: Any, b: Any) -> bool:
    return bool(_norm(a) and _norm(a) == _norm(b))


def _features(post: dict[str, Any]) -> dict[str, Any]:
    text = str(post.get("text") or post.get("body") or post.get("content") or "")
    low = text.casefold()
    return {
        "format": str(post.get("format") or post.get("media_type") or "unknown").casefold(),
        "text_length_chars": len(text),
        "has_cashtag": bool(re.search(r"\$[A-Za-z0-9]{2,15}", text)),
        "has_question": "?" in text,
        "has_numeric_evidence": bool(re.search(r"\d", text)),
        "has_source_link": bool(post.get("source_urls") or re.search(r"https?://", text)),
        "has_risk_or_invalidation_language": any(
            term in low for term in ("risk", "invalidation", "invalidated", "unless", "downside", "however", "could fail")
        ),
        "has_explicit_counterpoint": any(term in low for term in ("however", "on the other hand", "bear case", "counterpoint", "but if")),
        "topic": str(post.get("topic") or post.get("asset_or_topic") or "unspecified"),
    }


def _aggregate(posts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_features(p) for p in posts]
    count = len(rows)
    if not count:
        return {
            "post_count": 0,
            "format_counts": {},
            "topic_counts": {},
            "rates": {},
            "mean_text_length_chars": None,
            "observed_patterns": [],
        }
    formats = Counter(r["format"] for r in rows)
    topics = Counter(r["topic"] for r in rows)
    keys = (
        "has_cashtag", "has_question", "has_numeric_evidence", "has_source_link",
        "has_risk_or_invalidation_language", "has_explicit_counterpoint",
    )
    rates = {key: round(sum(bool(r[key]) for r in rows) / count, 4) for key in keys}
    patterns = []
    if rates["has_numeric_evidence"] >= 0.6:
        patterns.append("Many sampled posts include numeric evidence; verify relevance and source freshness rather than adding numbers mechanically.")
    if rates["has_risk_or_invalidation_language"] >= 0.5:
        patterns.append("Risk or invalidation language appears frequently in this sample.")
    if rates["has_question"] >= 0.5:
        patterns.append("Questions appear frequently; distinguish genuine discussion prompts from engagement bait.")
    if rates["has_source_link"] >= 0.5:
        patterns.append("Source links appear frequently; validate primary-source quality and timestamps.")
    if len(formats) > 1:
        patterns.append("The sample uses multiple formats; select format based on the idea, not a fixed rotation.")
    return {
        "post_count": count,
        "format_counts": dict(sorted(formats.items())),
        "topic_counts": dict(sorted(topics.items(), key=lambda x: (-x[1], x[0]))[:12]),
        "rates": rates,
        "mean_text_length_chars": round(sum(r["text_length_chars"] for r in rows) / count, 1),
        "observed_patterns": patterns,
    }


def build_learning_artifact(
    leaderboard: dict[str, Any],
    post_input: dict[str, Any],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build creator-period cohort observations and a strict coverage report."""
    generated_at_utc = generated_at_utc or datetime.now(timezone.utc).isoformat()
    entries = leaderboard.get("entries") or []
    posts = post_input.get("posts") or []
    collections = post_input.get("creator_collections") or []
    by_creator_collection: dict[str, dict[str, Any]] = {}
    for collection in collections:
        name = str(collection.get("creator") or "")
        if name:
            by_creator_collection[_norm(name)] = collection

    creators = []
    coverage = {"leaderboard_creators": len(entries), "identity_verified": 0, "complete_7d": 0, "complete_14d": 0, "missing_or_partial": 0}
    period_rewards: list[float] = []
    for entry in entries:
        name = str(entry.get("creator") or "")
        period_start = _parse_date(entry.get("period_start"))
        period_end = _parse_date(entry.get("period_end"))
        reward = entry.get("displayed_amount")
        collection = by_creator_collection.get(_norm(name), {})
        identity_verified = collection.get("identity_match") == "verified"
        if identity_verified:
            coverage["identity_verified"] += 1
        all_creator_posts = [
            p for p in posts
            if _creator_match(p.get("creator"), name)
            and (not collection.get("profile_url") or p.get("creator_profile_url") == collection.get("profile_url"))
        ]
        seven_start = period_start
        fourteen_start = (period_end - timedelta(days=13)) if period_end else None
        def in_window(post: dict[str, Any], start: datetime | None, end: datetime | None) -> bool:
            stamp = _parse_date(post.get("published_at_utc") or post.get("published_at") or post.get("created_at"))
            return bool(stamp and start and end and start <= stamp <= end)
        posts_7d = [p for p in all_creator_posts if in_window(p, seven_start, period_end)]
        posts_14d = [p for p in all_creator_posts if in_window(p, fourteen_start, period_end)]
        collection_status = str(collection.get("collection_status") or "missing")
        complete_7d = identity_verified and collection_status == "complete" and collection.get("window_7d_complete") is True
        complete_14d = identity_verified and collection_status == "complete" and collection.get("window_14d_complete") is True
        if complete_7d:
            coverage["complete_7d"] += 1
        if complete_14d:
            coverage["complete_14d"] += 1
        if not (complete_7d and complete_14d):
            coverage["missing_or_partial"] += 1
        if isinstance(reward, (int, float)):
            period_rewards.append(float(reward))
        creators.append({
            "creator": name,
            "rank": entry.get("rank"),
            "creator_period_reward": {
                "amount": reward,
                "currency": entry.get("currency"),
                "period_start": entry.get("period_start"),
                "period_end": entry.get("period_end"),
                "source_url": entry.get("source_url"),
                "evidence_ref": entry.get("evidence_ref"),
                "granularity": "creator_period_only",
                "verified_observation_note": entry.get("observation_note"),
            },
            "profile": {
                "url": collection.get("profile_url"),
                "identity_match": collection.get("identity_match", "unverified"),
                "collection_status": collection_status,
                "window_7d_complete": complete_7d,
                "window_14d_complete": complete_14d,
            },
            "post_cohort_7d": {
                "window_start_utc": entry.get("period_start"),
                "window_end_utc": entry.get("period_end"),
                **_aggregate(posts_7d),
            },
            "post_cohort_14d": {
                "window_start_utc": fourteen_start.isoformat() if fourteen_start else None,
                "window_end_utc": entry.get("period_end"),
                **_aggregate(posts_14d),
            },
            "attribution_policy": "Creator-period reward is NOT attributed to any individual post. Post features are descriptive cohort observations only.",
        })

    eligible = [c for c in creators if c["profile"]["identity_match"] == "verified" and c["profile"]["window_7d_complete"]]
    eligible_sorted = sorted(eligible, key=lambda c: float(c["creator_period_reward"].get("amount") or 0), reverse=True)
    split = len(eligible_sorted) // 2
    high_group = eligible_sorted[:split] if split else []
    lower_group = eligible_sorted[split:] if split else []

    def cohort_posts(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            p for p in posts
            if any(_creator_match(p.get("creator"), c["creator"]) and in_period_for_creator(p, c, "post_cohort_7d") for c in group)
        ]

    high_posts = cohort_posts(high_group)
    lower_posts = cohort_posts(lower_group)
    comparison_ready = len(high_group) >= 2 and len(lower_group) >= 2
    pooled = cohort_posts(eligible)
    return {
        "schema_version": 1,
        "artifact_type": "creator_period_cohort_learning",
        "generated_at_utc": generated_at_utc,
        "source_files": {
            "leaderboard": str(LEADERBOARD_PATH.relative_to(ROOT)),
            "post_input": str(POSTS_INPUT_PATH.relative_to(ROOT)),
        },
        "reward_granularity": "creator_period",
        "learning_status": "COHORT_HYPOTHESES_READY" if comparison_ready else "BLOCKED_INSUFFICIENT_VERIFIED_COVERAGE",
        "coverage": coverage,
        "creator_periods": creators,
        "cross_creator_post_cohort": _aggregate(pooled),
        "reward_tier_cohort_comparison": {
            "status": "DESCRIPTIVE_COMPARISON_AVAILABLE" if comparison_ready else "BLOCKED_NEED_AT_LEAST_TWO_CREATORS_PER_TIER_WITH_COMPLETE_7D_COVERAGE",
            "interpretation": "Compare post cohorts from higher-reward and lower-reward creators for descriptive hypotheses only. The weekly amount belongs to the creator-period, not to any sampled post.",
            "high_reward_creator_periods": {
                "creator_count": len(high_group),
                "creators": [c["creator"] for c in high_group],
                "cohort": _aggregate(high_posts),
            },
            "lower_reward_creator_periods": {
                "creator_count": len(lower_group),
                "creators": [c["creator"] for c in lower_group],
                "cohort": _aggregate(lower_posts),
            },
            "causal_claim": "NOT_SUPPORTED_BY_CREATOR_PERIOD_REWARDS",
        },
        "rules": [
            "Never divide creator-period rewards by post count or attach the total to a post.",
            "A creator is covered only when profile identity is verified and the collection manifest explicitly confirms the complete time window.",
            "A zero-post period counts as complete only when a successful, exhaustive collection is explicitly recorded.",
            "Observed post patterns are hypotheses, not causal proof that any one format earned the reward.",
            "Use this artifact in generation only when its coverage and learning status are explicit; otherwise fall back to the static playbook without claiming reward learning.",
        ],
    }


def in_period_for_creator(post: dict[str, Any], creator: dict[str, Any], cohort_key: str) -> bool:
    cohort = creator.get(cohort_key) or {}
    stamp = _parse_date(post.get("published_at_utc") or post.get("published_at") or post.get("created_at"))
    start, end = _parse_date(cohort.get("window_start_utc")), _parse_date(cohort.get("window_end_utc"))
    return bool(stamp and start and end and start <= stamp <= end)


def run() -> dict[str, Any]:
    leaderboard = _read_json(LEADERBOARD_PATH)
    post_input = _read_json(POSTS_INPUT_PATH)
    artifact = build_learning_artifact(leaderboard, post_input)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


if __name__ == "__main__":
    artifact = run()
    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "learning_status": artifact["learning_status"],
        "coverage": artifact["coverage"],
    }, ensure_ascii=False, indent=2))
