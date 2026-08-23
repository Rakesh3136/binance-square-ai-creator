import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MEMORY = Path("analytics/strategy_memory.json")
PUBLICATION_LOG = Path("analytics/publication_log.jsonl")
METRICS = Path("analytics/post_metrics.jsonl")
CREATOR_PATTERNS = Path("data/intelligence/creator_patterns.json")
REPORT = Path("data/live/learning_report.json")


def read_json(path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except Exception:
        return default


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            continue
    return rows


def num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def norm_symbol(value):
    value = str(value or "").upper().strip()
    value = value.replace("USDT", "")
    return re.sub(r"[^A-Z0-9]", "", value)


def engagement_score(row):
    views = max(num(row.get("views")), 1.0)
    likes = max(num(row.get("likes")), 0.0)
    replies = max(num(row.get("replies")), 0.0)
    shares = max(num(row.get("shares")), 0.0)
    followers = max(num(row.get("followers_gained")), 0.0)
    # Replies and follows are intentionally weighted much more than passive views.
    return ((likes * 0.5) + (replies * 4.0) + (shares * 2.0) + (followers * 6.0)) / views * 100.0


def style_from(row):
    return str(row.get("editorial_style") or row.get("experiment_format") or row.get("format") or "unknown").strip().lower()


def main():
    memory = read_json(MEMORY, {})
    publications = read_jsonl(PUBLICATION_LOG)
    metrics = read_jsonl(METRICS)
    patterns = read_json(CREATOR_PATTERNS, {})

    by_id = {str(x.get("post_id")): x for x in publications if x.get("post_id")}
    observations = []
    for metric in metrics:
        post_id = str(metric.get("post_id") or "")
        pub = by_id.get(post_id, {})
        merged = {**pub, **metric}
        merged["symbol"] = norm_symbol(merged.get("symbol") or merged.get("selected_lane_symbol"))
        merged["style"] = style_from(merged)
        merged["engagement_score"] = round(engagement_score(merged), 4)
        observations.append(merged)

    # Also retain historical observations already stored in strategy memory.
    historical = memory.get("recent_performance_observations") or []
    combined = []
    for row in historical:
        if isinstance(row, dict):
            x = dict(row)
            x["engagement_score"] = round(engagement_score(x), 4)
            combined.append(x)
    combined.extend(observations)

    # Deduplicate by post id when available; otherwise preserve the newest observations.
    seen = set()
    deduped = []
    for row in reversed(combined):
        key = str(row.get("post_id") or f"{row.get('topic')}|{row.get('views')}|{row.get('replies')}|{row.get('published_at')}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped = list(reversed(deduped))[-30:]

    style_groups = defaultdict(list)
    topic_groups = defaultdict(list)
    for row in deduped:
        style_groups[row.get("style", "unknown")].append(row)
        topic_groups[norm_symbol(row.get("symbol") or row.get("topic"))].append(row)

    style_stats = []
    for style, rows in style_groups.items():
        if not style or style == "unknown":
            continue
        style_stats.append({
            "style": style,
            "samples": len(rows),
            "avg_views": round(sum(num(r.get("views")) for r in rows) / len(rows), 2),
            "avg_replies": round(sum(num(r.get("replies")) for r in rows) / len(rows), 3),
            "avg_followers": round(sum(num(r.get("followers_gained")) for r in rows) / len(rows), 3),
            "avg_engagement_score": round(sum(num(r.get("engagement_score")) for r in rows) / len(rows), 4),
        })
    style_stats.sort(key=lambda x: (x["avg_replies"], x["avg_followers"], x["avg_engagement_score"]), reverse=True)

    avoid = []
    for symbol, rows in topic_groups.items():
        if not symbol:
            continue
        if len(rows) >= 2 and all(num(r.get("replies")) == 0 and num(r.get("followers_gained")) == 0 for r in rows[-3:]):
            avoid.append({"symbol": symbol, "samples": len(rows), "reason": "Repeated passive views with zero replies and zero follower conversion."})

    public_patterns = patterns.get("patterns") or []
    if not public_patterns:
        public_patterns = [
            {"pattern": "Trend-aligned useful insight", "hypothesis": "Timely, useful content is more likely to earn attention than generic recaps."},
            {"pattern": "Cashtag + chart widget", "hypothesis": "Cashtags and chart widgets can connect readers to trading activity for Write to Earn attribution."},
            {"pattern": "Specific debate question", "hypothesis": "A concrete binary or multi-choice question lowers the effort required to reply."},
            {"pattern": "Format diversity", "hypothesis": "Rotating formats reduces audience fatigue and creates more experiments."},
        ]

    winners = style_stats[:3]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "observation_count": len(observations),
        "total_learning_samples": len(deduped),
        "metrics_source": "analytics/post_metrics.jsonl",
        "creator_pattern_source": "data/intelligence/creator_patterns.json",
        "top_styles": winners,
        "avoid_assets": avoid,
        "public_creator_hypotheses": public_patterns,
        "next_experiment_rule": "Prefer under-tested formats; penalize styles/assets with repeated zero-reply and zero-follower outcomes; never declare a winner from one sample.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    updated = dict(memory)
    updated["version"] = max(int(memory.get("version", 1)), 4)
    updated["generated_at"] = datetime.now(timezone.utc).isoformat()
    updated["sample_size"] = len(deduped)
    updated["recent_performance_observations"] = [
        {k: row.get(k) for k in ("post_id", "topic", "symbol", "views", "likes", "replies", "shares", "followers_gained", "style", "engagement_score") if row.get(k) is not None}
        for row in deduped[-20:]
    ]
    updated["best_formats"] = winners
    updated["avoid_patterns"] = (memory.get("avoid_patterns") or []) + [
        {"pattern": f"Repeated zero-reply asset: {x['symbol']}", "reason": x["reason"], "rule": "Apply a strong repetition penalty until a materially different format proves otherwise."}
        for x in avoid
    ]
    updated["creator_pattern_hypotheses"] = public_patterns
    updated["recommended_strategy"] = (
        "Run a two-loop editorial system: learn from our measured post outcomes and from public creator patterns. "
        "Use public patterns as hypotheses, never as copied templates. Prioritize replies and follower conversion over raw views. "
        "Keep testing different assets, hooks, formats, visuals and questions; retire repeated zero-conversion patterns."
    )
    MEMORY.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
