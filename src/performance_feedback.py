"""Creator 4.4 performance -> strategy feedback.

Consumes only recorded/verified observations. Produces reusable strategy signals for
story selection and writing. It never invents metrics or claims knowledge of a
platform's private ranking algorithm.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRATEGY = ROOT / "analytics/strategy_memory.json"
AUDIENCE = ROOT / "data/intelligence/audience_profile.json"
OUT = ROOT / "data/intelligence/performance_feedback.json"


def read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(item: dict, *keys: str) -> float:
    for key in keys:
        value = item.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


def key(item: dict, *keys: str) -> str:
    for k in keys:
        value = str(item.get(k) or "").strip()
        if value:
            return value
    return "unknown"


def aggregate(rows, field_names):
    buckets = defaultdict(lambda: {"posts": 0, "views": 0.0, "likes": 0.0, "replies": 0.0, "followers": 0.0})
    for row in rows:
        label = key(row, *field_names)
        b = buckets[label]
        b["posts"] += 1
        b["views"] += num(row, "views", "viewCount")
        b["likes"] += num(row, "likes", "likeCount")
        b["replies"] += num(row, "replies", "replyCount", "comments")
        b["followers"] += num(row, "followers_gained", "followersGained", "new_followers")
    out = []
    for label, b in buckets.items():
        views = b["views"]
        reply_rate = b["replies"] / views if views else 0.0
        follow_rate = b["followers"] / views if views else 0.0
        engagement = reply_rate * 1000 + follow_rate * 5000
        out.append({"key": label, **b, "reply_rate": round(reply_rate, 6), "follow_rate": round(follow_rate, 6), "performance_score": round(engagement, 4)})
    return sorted(out, key=lambda x: (x["performance_score"], x["views"]), reverse=True)


def main() -> None:
    strategy = read(STRATEGY)
    audience = read(AUDIENCE)
    observations = strategy.get("recent_observations") or strategy.get("recent_performance_observations") or []
    observations = [x for x in observations if isinstance(x, dict)][-50:]

    scored = []
    for x in observations:
        views = num(x, "views", "viewCount")
        replies = num(x, "replies", "replyCount", "comments")
        followers = num(x, "followers_gained", "followersGained", "new_followers")
        likes = num(x, "likes", "likeCount")
        scored.append({
            "symbol": key(x, "symbol", "topic").upper().replace("USDT", ""),
            "format": key(x, "editorial_format", "format", "experiment_format"),
            "category": key(x, "category", "content_category", "lane"),
            "style": key(x, "editorial_style", "style", "voice"),
            "hook_type": key(x, "hook_type", "hook_pattern", "hook"),
            "views": views, "replies": replies, "followers_gained": followers, "likes": likes,
            "reply_rate": replies / views if views else 0.0,
            "follow_rate": followers / views if views else 0.0,
            "has_verified_metrics": bool(x.get("metrics_verified", x.get("verified", False))),
        })

    verified = [x for x in scored if x["has_verified_metrics"] and x["views"] > 0]
    minimum_sample = 3
    dimensions = {
        "format": aggregate(verified, ("format",)),
        "category": aggregate(verified, ("category",)),
        "style": aggregate(verified, ("style",)),
        "hook_type": aggregate(verified, ("hook_type",)),
    }
    winners = [x for x in verified if x["replies"] > 0 or x["followers_gained"] > 0]
    low_conversion = [x for x in verified if x["views"] > 100 and x["replies"] == 0 and x["followers_gained"] == 0]

    # Promote a dimension only when it has repeated evidence, not because one post won.
    learned_preferences = {}
    for dimension, rows in dimensions.items():
        repeated = [r for r in rows if r["posts"] >= minimum_sample]
        if repeated:
            best = repeated[0]
            learned_preferences[dimension] = {
                "prefer": best["key"],
                "sample": best["posts"],
                "performance_score": best["performance_score"],
                "reply_rate": best["reply_rate"],
                "follow_rate": best["follow_rate"],
            }
        else:
            learned_preferences[dimension] = {"prefer": None, "reason": "insufficient_repeated_evidence"}

    audience_signals = audience.get("signals") or {}
    feedback = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": len(scored),
        "verified_observation_count": len(verified),
        "minimum_sample_for_promotion": minimum_sample,
        "promotion_allowed": len(verified) >= minimum_sample,
        "winner_count": len(winners),
        "high_reach_low_conversion_count": len(low_conversion),
        "top_verified_posts": sorted(verified, key=lambda x: (x["replies"] / max(1, x["views"]) * 1000 + x["followers_gained"] / max(1, x["views"]) * 5000), reverse=True)[:10],
        "dimension_leaderboards": dimensions,
        "learned_preferences": learned_preferences,
        "audience_signals": audience_signals,
        "next_cycle_policy": {
            "use_performance_as_a_tiebreaker": True,
            "prefer_repeatedly_proven_formats_styles_and_hooks": True,
            "explore_when_evidence_is_sparse": len(verified) < minimum_sample,
            "do_not_promote_single_post_winner": True,
            "do_not_treat_views_as_conversion": True,
            "do_not_invent_missing_metrics": True,
            "never_trade_accuracy_for_engagement": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(feedback, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "observations": len(scored), "verified": len(verified), "winners": len(winners), "low_conversion": len(low_conversion), "promotion_allowed": feedback["promotion_allowed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
