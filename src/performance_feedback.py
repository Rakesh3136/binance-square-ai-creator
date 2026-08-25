"""Build a conservative performance feedback packet from verified observations.

This module never invents metrics. It only consumes metrics already recorded by the
publication/learning system and turns them into explicit next-cycle signals.
"""
from __future__ import annotations

import json
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


def main() -> None:
    strategy = read(STRATEGY)
    audience = read(AUDIENCE)
    observations = strategy.get("recent_observations") or strategy.get("recent_performance_observations") or []
    observations = [x for x in observations if isinstance(x, dict)][-30:]

    scored = []
    for x in observations:
        views = num(x, "views", "viewCount")
        replies = num(x, "replies", "replyCount")
        followers = num(x, "followers_gained", "followersGained", "new_followers")
        likes = num(x, "likes", "likeCount")
        scored.append({
            "symbol": str(x.get("symbol", "")).upper().replace("USDT", ""),
            "format": str(x.get("editorial_format", x.get("format", ""))),
            "category": str(x.get("category", "")),
            "views": views,
            "replies": replies,
            "followers_gained": followers,
            "likes": likes,
            "reply_rate": replies / views if views else 0.0,
            "follow_rate": followers / views if views else 0.0,
            "has_verified_metrics": bool(x.get("metrics_verified", x.get("verified", False))),
        })

    verified = [x for x in scored if x["has_verified_metrics"]]
    minimum_sample = 3
    winners = []
    losers = []
    for x in verified:
        if x["views"] <= 0:
            continue
        engagement = x["reply_rate"] * 1000 + x["follow_rate"] * 5000
        if x["replies"] > 0 or x["followers_gained"] > 0:
            winners.append({**x, "engagement_score": round(engagement, 4)})
        elif x["views"] > 100:
            losers.append({**x, "engagement_score": round(engagement, 4)})

    winner_formats = {}
    loser_formats = {}
    for x in winners:
        key = x["format"] or "unknown"
        winner_formats[key] = winner_formats.get(key, 0) + 1
    for x in losers:
        key = x["format"] or "unknown"
        loser_formats[key] = loser_formats.get(key, 0) + 1

    audience_signals = audience.get("signals") or {}
    feedback = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": len(scored),
        "verified_observation_count": len(verified),
        "minimum_sample_for_winner_promotion": minimum_sample,
        "winner_promotion_allowed": len(verified) >= minimum_sample,
        "winner_count": len(winners),
        "high_reach_low_conversion_count": len(losers),
        "top_verified_winners": sorted(winners, key=lambda x: x["engagement_score"], reverse=True)[:10],
        "winner_formats": winner_formats,
        "loser_formats": loser_formats,
        "audience_signals": audience_signals,
        "next_cycle_policy": {
            "prioritize_reply_generating_formats": bool(winners),
            "explore_before_exploiting": len(verified) < minimum_sample,
            "do_not_promote_single_post_winner": True,
            "do_not_treat_views_as_conversion": True,
            "do_not_invent_missing_metrics": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(feedback, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "observations": len(scored),
        "verified": len(verified),
        "winners": len(winners),
        "low_conversion": len(losers),
        "winner_promotion_allowed": feedback["winner_promotion_allowed"],
    }))


if __name__ == "__main__":
    main()
