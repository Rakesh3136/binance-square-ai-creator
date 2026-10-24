"""Study public creator posts against first-party weekly Write-to-Earn displayed earnings.

Weekly creator earnings are period-level outcomes. They are not attributed to each
post. This module joins a valid observed earnings row to public posts in the same
period and reports patterns for research; it never claims those posts caused earnings.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = ROOT / "data/intelligence/wte_leaderboard_observed.json"
PROFILE_RESEARCH = ROOT / "data/intelligence/nic_square_profile_research.json"
OUT = ROOT / "data/intelligence/nic_weekly_earner_study.json"


def read_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except ValueError:
        return None


def profile_slug(url):
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"binance.com", "www.binance.com"}:
        return None
    parts = parsed.path.strip("/").split("/")
    try:
        i = parts.index("profile")
        return parts[i + 1].casefold() if i + 1 < len(parts) else None
    except ValueError:
        return None


def post_matches_creator(post, slug):
    if not slug:
        return False
    url_slug = profile_slug(post.get("creator_profile_url"))
    if url_slug:
        return url_slug == slug
    return str(post.get("creator_username") or post.get("username") or "").strip().casefold() == slug


def study(observations, research, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    posts = research.get("posts", []) if isinstance(research, dict) else []
    entries = observations.get("entries", []) if isinstance(observations, dict) else []
    studies = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "VERIFIED_FIRST_PARTY_DISPLAYED_EARNINGS":
            continue
        start, end = parse_time(entry.get("period_start")), parse_time(entry.get("period_end"))
        if not start or not end or start > end:
            continue
        slug = profile_slug(entry.get("creator_profile_url"))
        matching = []
        for post in posts:
            if not isinstance(post, dict) or not post_matches_creator(post, slug):
                continue
            posted = parse_time(post.get("posted_at"))
            if posted and start <= posted <= end:
                matching.append(post)
        lookback_start = end - timedelta(days=14)
        lookback = []
        for post in posts:
            if not isinstance(post, dict) or not post_matches_creator(post, slug):
                continue
            posted = parse_time(post.get("posted_at"))
            if posted and lookback_start <= posted <= end:
                lookback.append(post)
        def summarize(window_posts):
            def distribution(field):
                return dict(Counter(str(p.get(field) or "unknown") for p in window_posts).most_common())
            return {
                "post_count": len(window_posts),
                "post_archetypes": distribution("archetype"),
                "post_formats": distribution("format"),
                "posts": [{
                    "post_id": p.get("post_id"),
                    "post_url": p.get("source_url"),
                    "posted_at": p.get("posted_at"),
                    "archetype": p.get("archetype"),
                    "format": p.get("format"),
                    "views": p.get("views"),
                    "likes": p.get("likes"),
                    "replies": p.get("replies"),
                    "shares": p.get("shares"),
                } for p in window_posts],
                "history_sufficient_for_pattern_claims": bool(window_posts),
                "empty_history_reason": None if window_posts else "NO_MATCHING_CREATOR_POSTS_RETRIEVED_FOR_THIS_WINDOW",
            }
        studies.append({
            "creator": entry.get("creator"),
            "creator_profile_url": entry.get("creator_profile_url"),
            "displayed_amount": entry.get("displayed_amount"),
            "currency": entry.get("currency"),
            "rank": entry.get("rank"),
            "period_start": entry.get("period_start"),
            "period_end": entry.get("period_end"),
            "leaderboard_source_url": entry.get("source_url"),
            "leaderboard_evidence_ref": entry.get("evidence_ref"),
            "evidence_type": "FIRST_PARTY_WRITE_TO_EARN_DISPLAY",
            "posts_found_in_earnings_period": len(matching),
            "exact_earnings_period": summarize(matching),
            "fourteen_day_lookback": {
                "start": lookback_start.isoformat(),
                "end": end.isoformat(),
                **summarize(lookback),
            },
            "interpretation": "Creator-level earnings are displayed for this period; individual post earnings are unknown. Post patterns are hypotheses to test, not causal attribution.",
            "independently_verified_payment": False,
            "individual_post_reward_attribution": False,
        })
    return {
        "schema": "NIC-WEEKLY-EARNER-STUDY-1.0",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "status": "WEEKLY_EARNER_STUDY_READY" if studies else "NO_VALID_WEEKLY_EARNER_OBSERVATIONS",
        "source_observation_count": len(entries),
        "creator_periods_studied": len(studies),
        "creator_periods_with_exact_period_posts": sum(s["exact_earnings_period"]["post_count"] > 0 for s in studies),
        "creator_periods_with_14_day_posts": sum(s["fourteen_day_lookback"]["post_count"] > 0 for s in studies),
        "studies": studies,
        "policy": {
            "requires_first_party_observed_earnings": True,
            "reports_exact_earnings_period_separately_from_14_day_lookback": True,
            "matches_public_posts_only_to_creator_profile_and_dates": True,
            "empty_history_is_reported_not_filled_with_out_of_period_posts": True,
            "does_not_infer_per_post_earnings": True,
            "public_engagement_is_not_earnings": True,
            "missing_profile_url_means_no_creator_match": True,
        },
    }


def main():
    result = study(read_json(OBSERVED, {}), read_json(PROFILE_RESEARCH, {}))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "source_observation_count", "creator_periods_studied", "creator_periods_with_exact_period_posts", "creator_periods_with_14_day_posts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
