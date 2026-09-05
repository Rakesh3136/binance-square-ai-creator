"""Creator 7.2 — Outcome/Revenue Learning.

Every published decision becomes an experiment. This module joins publication
metadata with verified Square observations, diagnoses why an experiment won or
lost, and writes a conservative strategy overlay consumed by future creator
runs.

Revenue is never inferred from views/likes. It is used only when a verified
revenue/earnings field is explicitly present in recorded account evidence.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "analytics/publication_log.jsonl"
PERF = ROOT / "analytics/square_performance.jsonl"
OUT = ROOT / "analytics/creator_7_2_outcomes.jsonl"
STATE = ROOT / "analytics/creator_7_2_state.json"
STRATEGY = ROOT / "analytics/creator_7_2_strategy.json"
REPORT = ROOT / "data/intelligence/creator_7_2_report.json"


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict): rows.append(value)
        except Exception:
            pass
    return rows


def num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return 0.0


def first_num(row, keys):
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def pid(row):
    for key in ("post_id", "id", "content_id", "publication_id"):
        value = row.get(key)
        if value is not None and str(value).strip(): return str(value)
    return ""


def metric(record, key):
    metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
    aliases = {
        "views": ("views", "viewCount"),
        "likes": ("likes", "likeCount"),
        "comments": ("comments", "commentCount", "replyCount"),
        "shares": ("shares", "shareCount"),
        "quotes": ("quotes", "quoteCount"),
        "followers": ("followers_gained", "followersGained", "new_followers"),
    }
    for source in (record, metrics):
        for k in aliases[key]:
            if k in source and source[k] not in (None, ""):
                return num(source[k])
    return 0.0


def dimensions(pub):
    exp = pub.get("experiment") if isinstance(pub.get("experiment"), dict) else {}
    return {
        "experiment_id": str(pub.get("experiment_id") or exp.get("id") or pub.get("recommended_experiment") or "unknown"),
        "experiment_format": str(pub.get("experiment_format") or exp.get("format") or pub.get("format") or "unknown"),
        "category": str(pub.get("content_category") or pub.get("category") or pub.get("lane") or "unknown"),
        "style": str(pub.get("editorial_style") or pub.get("style") or "unknown"),
        "symbol": str(pub.get("symbol") or "unknown").upper(),
        "hook_type": str(pub.get("hook_type") or pub.get("hook_pattern") or "unknown"),
        "visual_type": str(pub.get("visual_type") or pub.get("chart_type") or "unknown"),
    }


def score(m):
    views, likes, comments, shares, followers = (m[k] for k in ("views", "likes", "comments", "shares", "followers"))
    if views <= 0: return 0.0
    # Weighted outcome score: meaningful actions matter more than raw reach.
    engagement = (likes + 2 * comments + 3 * shares) / views * 100
    growth = followers / views * 100
    return round(0.55 * min(100.0, engagement * 20) + 0.45 * min(100.0, growth * 50), 4)


def diagnosis(outcome, peer):
    m = outcome["metrics"]
    views = m["views"]
    reach = views / max(peer.get("median_views", views), 1)
    reply_rate = m["comments"] / max(views, 1)
    share_rate = m["shares"] / max(views, 1)
    follow_rate = m["followers"] / max(views, 1)
    score_delta = outcome["outcome_score"] - peer.get("median_score", outcome["outcome_score"])

    reasons = []
    if reach >= 1.25: reasons.append("above_baseline_reach")
    elif reach <= 0.75: reasons.append("below_baseline_reach")
    if reply_rate >= peer.get("median_reply_rate", reply_rate) * 1.25 and reply_rate > 0: reasons.append("strong_discussion_conversion")
    elif reply_rate <= peer.get("median_reply_rate", reply_rate) * 0.75: reasons.append("weak_discussion_conversion")
    if share_rate >= peer.get("median_share_rate", share_rate) * 1.25 and share_rate > 0: reasons.append("strong_share_conversion")
    if follow_rate >= peer.get("median_follow_rate", follow_rate) * 1.25 and follow_rate > 0: reasons.append("strong_follower_conversion")
    if score_delta >= 10: reasons.append("outcome_score_above_baseline")
    elif score_delta <= -10: reasons.append("outcome_score_below_baseline")
    if not reasons: reasons.append("mixed_or_insufficient_signal")

    if "strong_follower_conversion" in reasons or "strong_discussion_conversion" in reasons:
        verdict = "WIN"
    elif "below_baseline_reach" in reasons and "weak_discussion_conversion" in reasons:
        verdict = "LOSS"
    elif score_delta >= 10:
        verdict = "WIN"
    elif score_delta <= -10:
        verdict = "LOSS"
    else:
        verdict = "MIXED"
    return verdict, reasons


def aggregate(rows):
    buckets = defaultdict(list)
    for row in rows:
        for dim in ("experiment_id", "experiment_format", "category", "style", "hook_type", "visual_type"):
            buckets[(dim, row[dim])].append(row)
    return buckets


def median(values):
    xs = sorted(values)
    if not xs: return 0.0
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def main():
    publications = [x for x in jsonl(PUB) if pid(x)]
    performance = [x for x in jsonl(PERF) if pid(x)]
    latest = {}
    for row in performance:
        latest[pid(row)] = row

    state = read_json(STATE, {"processed": []})
    processed = set(str(x) for x in state.get("processed", []))
    joined = []
    for pub in publications:
        post = pid(pub)
        if post not in latest: continue
        perf = latest[post]
        d = dimensions(pub)
        metrics = {k: metric(perf, k) for k in ("views", "likes", "comments", "shares", "quotes", "followers")}
        if metrics["views"] <= 0: continue
        row = {**d, "post_id": post, "published_at": pub.get("published_at") or pub.get("recorded_at"), "metrics": metrics}
        row["outcome_score"] = score(metrics)
        # Revenue is accepted only from explicit verified account evidence attached to the record.
        revenue = first_num(perf, ("revenue_verified", "verified_revenue", "earnings_verified", "verified_earnings"))
        row["verified_revenue"] = revenue
        row["revenue_source"] = perf.get("revenue_source") if revenue is not None else None
        joined.append(row)

    # Cross-post baseline prevents the engine from calling a post a winner just because it has large raw numbers.
    all_scores = [x["outcome_score"] for x in joined]
    global_peer = {
        "median_views": median([x["metrics"]["views"] for x in joined]),
        "median_score": median(all_scores),
        "median_reply_rate": median([x["metrics"]["comments"] / max(1, x["metrics"]["views"]) for x in joined]),
        "median_share_rate": median([x["metrics"]["shares"] / max(1, x["metrics"]["views"]) for x in joined]),
        "median_follow_rate": median([x["metrics"]["followers"] / max(1, x["metrics"]["views"]) for x in joined]),
    }

    buckets = aggregate(joined)
    leaders = []
    for (dim, value), rows in buckets.items():
        if len(rows) < 3: continue
        leaders.append({"dimension": dim, "value": value, "sample": len(rows), "median_score": round(median([r["outcome_score"] for r in rows]), 4), "median_views": round(median([r["metrics"]["views"] for r in rows]), 2)})
    leaders.sort(key=lambda x: (x["median_score"], x["sample"]), reverse=True)

    outcomes = []
    for row in joined:
        verdict, reasons = diagnosis(row, global_peer)
        outcome = {**row, "verdict": verdict, "reasons": reasons, "baseline": global_peer}
        outcomes.append(outcome)

    # Conservative strategy changes: only repeated evidence (>=3) is allowed to change preference.
    wins = [x for x in outcomes if x["verdict"] == "WIN"]
    losses = [x for x in outcomes if x["verdict"] == "LOSS"]
    preference_changes = []
    for dim in ("experiment_id", "experiment_format", "category", "style", "hook_type", "visual_type"):
        groups = defaultdict(list)
        for row in outcomes: groups[row[dim]].append(row)
        candidates = []
        for value, rows in groups.items():
            if len(rows) < 3: continue
            candidates.append((median([r["outcome_score"] for r in rows]), value, len(rows)))
        if candidates:
            best = max(candidates)
            worst = min(candidates)
            preference_changes.append({"dimension": dim, "prefer": best[1], "prefer_median_score": round(best[0], 4), "prefer_sample": best[2], "avoid": worst[1] if worst[2] >= 3 and worst[0] < best[0] else None})

    revenue_rows = [x for x in outcomes if x.get("verified_revenue") is not None]
    revenue_summary = {
        "verified": bool(revenue_rows),
        "sample": len(revenue_rows),
        "total": round(sum(x["verified_revenue"] for x in revenue_rows), 8),
        "note": "Revenue is never estimated from engagement metrics. Only explicitly verified earnings fields are used."
    }

    strategy = {
        "version": "7.2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "learning_status": "ACTIVE" if len(outcomes) >= 3 else "EXPLORATION",
        "experiment_rule": "Every published decision is an experiment; outcomes are evaluated against the creator's own baseline.",
        "sample_size": len(outcomes),
        "wins": len(wins), "losses": len(losses), "mixed": len(outcomes) - len(wins) - len(losses),
        "preference_changes": preference_changes,
        "revenue": revenue_summary,
        "next_strategy": {
            "prefer": [x for x in preference_changes if x.get("prefer")][:8],
            "avoid": [x for x in preference_changes if x.get("avoid")][:8],
            "exploration_rate": 0.20 if len(outcomes) >= 10 else 0.35,
            "minimum_repeated_sample": 3,
            "never_promote_single_post": True,
            "revenue_must_be_verified": True,
            "accuracy_and_originality_are_hard_constraints": True,
        },
    }

    now = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for row in outcomes:
            if row["post_id"] in processed: continue
            f.write(json.dumps({"learned_at": now, **row}, ensure_ascii=False) + "\n")
    STATE.write_text(json.dumps({"last_run": now, "processed": sorted({*processed, *(x["post_id"] for x in outcomes)})}, indent=2), encoding="utf-8")
    STRATEGY.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"version": "7.2", "generated_at": now, "global_baseline": global_peer, "outcomes": outcomes[-50:], "leaderboards": leaders[:30], "strategy": strategy}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "version": "7.2", "published_experiments_observed": len(outcomes), "wins": len(wins), "losses": len(losses), "mixed": len(outcomes)-len(wins)-len(losses), "strategy": str(STRATEGY), "report": str(REPORT), "verified_revenue_samples": len(revenue_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
