"""Creator 22.0 — audience intelligence and closed-loop learning.

Turns durable publication records + verified performance snapshots into an
explainable learning board. It never invents metrics, revenue, causality, or
engagement. It only changes strategy when evidence is sufficient.
"""
from __future__ import annotations
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/publication_log.jsonl"
PERF = ROOT / "data/intelligence/performance_feedback.json"
OUTCOMES = ROOT / "data/live/creator_7_2_outcomes.jsonl"
STRATEGY = ROOT / "data/intelligence/creator_strategy_memory.json"
BOARD = ROOT / "data/live/creator_22_0_audience_board.json"
REPORT = ROOT / "data/intelligence/creator_22_0_report.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def rows(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            value = json.loads(line)
            if isinstance(value, dict): out.append(value)
        except Exception:
            continue
    return out


def metric(row, *names):
    for name in names:
        if name in row and row[name] is not None:
            try: return float(row[name])
            except (TypeError, ValueError): pass
    return None


def key(row):
    return (
        str(row.get("experiment_id") or "unknown"),
        str(row.get("format") or "unknown"),
        str(row.get("category") or "unknown"),
        str(row.get("hook_type") or "unknown"),
        str(row.get("visual_type") or "unknown"),
    )


def main():
    publications = rows(LOG)
    outcomes = rows(OUTCOMES)
    performance = load(PERF)
    strategy = load(STRATEGY)

    # Prefer durable outcome rows; publication metadata supplies the identity.
    samples = []
    for row in outcomes:
        views = metric(row, "views", "view_count")
        likes = metric(row, "likes", "like_count")
        replies = metric(row, "replies", "reply_count", "comments")
        shares = metric(row, "shares", "share_count")
        followers = metric(row, "followers_gained", "follower_growth")
        if views is None and likes is None and replies is None and shares is None and followers is None:
            continue
        samples.append({**row, "views": views, "likes": likes, "replies": replies, "shares": shares, "followers_gained": followers})

    groups = {}
    for row in samples:
        groups.setdefault(key(row), []).append(row)

    insights = []
    for k, group in groups.items():
        views = [x["views"] for x in group if x["views"] is not None]
        likes = [x["likes"] for x in group if x["likes"] is not None]
        replies = [x["replies"] for x in group if x["replies"] is not None]
        shares = [x["shares"] for x in group if x["shares"] is not None]
        followers = [x["followers_gained"] for x in group if x["followers_gained"] is not None]
        if len(group) < 3:
            confidence = "INSUFFICIENT"
        else:
            confidence = "OBSERVATIONAL"
        insights.append({
            "dimensions": {"experiment_id": k[0], "format": k[1], "category": k[2], "hook_type": k[3], "visual_type": k[4]},
            "samples": len(group),
            "avg_views": round(statistics.mean(views), 2) if views else None,
            "avg_likes": round(statistics.mean(likes), 2) if likes else None,
            "avg_replies": round(statistics.mean(replies), 2) if replies else None,
            "avg_shares": round(statistics.mean(shares), 2) if shares else None,
            "avg_followers_gained": round(statistics.mean(followers), 2) if followers else None,
            "confidence": confidence,
        })

    # Rank only by metrics actually supplied by the account/performance layer.
    ranked = sorted(insights, key=lambda x: (x["avg_views"] or 0, x["avg_replies"] or 0, x["avg_followers_gained"] or 0), reverse=True)
    winners = [x for x in ranked if x["samples"] >= 3][:5]
    losers = [x for x in reversed(ranked) if x["samples"] >= 3][:5]

    strategy_actions = []
    if winners:
        for winner in winners[:3]:
            strategy_actions.append({"action": "INCREASE_TESTING", "dimensions": winner["dimensions"], "reason": "repeated_observed_performance", "do_not_claim_causality": True})
    if losers:
        for loser in losers[:3]:
            strategy_actions.append({"action": "DECREASE_REPETITION", "dimensions": loser["dimensions"], "reason": "repeated_observed_underperformance", "do_not_delete_dimension": True})
    if not samples:
        strategy_actions.append({"action": "COLLECT_MORE_REAL_PERFORMANCE", "reason": "no_usable_verified_performance_rows"})

    board = {
        "version": "22.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "samples": len(samples),
        "performance_source_present": bool(performance),
        "publication_records_seen": len(publications),
        "observed_patterns": ranked[:20],
        "winners": winners,
        "underperformers": losers,
        "recommended_strategy_actions": strategy_actions,
        "rules": {
            "metrics_must_be_explicit": True,
            "views_are_not_revenue": True,
            "no_inferred_engagement": True,
            "no_causal_claims_from_observation": True,
            "minimum_repeated_samples_for_strategy_change": 3,
            "do_not_copy_individual_creators": True,
            "do_not_manipulate_engagement": True,
            "accuracy_over_growth": True,
        },
        "existing_strategy_version": strategy.get("version"),
    }
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(board, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"22.0","status":"OK","board":str(BOARD.relative_to(ROOT)),"samples":len(samples),"actions":len(strategy_actions)}, indent=2), encoding="utf-8")
    print(json.dumps(board, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
