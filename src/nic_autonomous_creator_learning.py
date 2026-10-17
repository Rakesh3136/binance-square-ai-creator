"""Evidence-bounded autonomous creator learning cycle.

Learns reusable editorial hypotheses from public Square observations and the
account's own exact-post metrics/reward events. This module does not train model
weights, alter source code, authorize trading, or publish content.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from src.nic_reward_evidence import canonical_post_id, is_verified_reward_event
except ModuleNotFoundError:
    from nic_reward_evidence import canonical_post_id, is_verified_reward_event

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "data/intelligence/public_square_examples.json"
PATTERNS = ROOT / "data/intelligence/creator_patterns.json"
ATTRIBUTION = ROOT / "analytics/publication_attribution.jsonl"
PERFORMANCE = ROOT / "analytics/square_performance.jsonl"
REWARD_EVENTS = ROOT / "analytics/wte_reward_events.jsonl"
OUT = ROOT / "data/intelligence/nic_autonomous_creator_learning.json"
REPORT = ROOT / "data/live/nic_autonomous_creator_learning_report.json"
MIN_PUBLIC_SAMPLES = 3
MIN_OWN_SAMPLES = 3


def read_json(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                continue
    return rows


def post_id(row: dict) -> str:
    raw = str(row.get("canonical_post_id") or row.get("post_id") or row.get("publication_id") or "").strip()
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw.lower()


def number(row: dict, *keys: str) -> float:
    for key in keys:
        try:
            value = float(row.get(key) or 0)
            if value >= 0 and value < float("inf"):
                return value
        except (TypeError, ValueError):
            continue
    return 0.0


def fingerprint(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    examples = read_json(EXAMPLES, [])
    examples = examples if isinstance(examples, list) else []
    patterns = read_json(PATTERNS, {})
    patterns = patterns if isinstance(patterns, dict) else {}

    public_groups: dict[str, list[dict]] = defaultdict(list)
    public_posts = []
    seen = set()
    for row in examples:
        if not isinstance(row, dict) or row.get("source_type") != "public_square_creator_observation":
            continue
        pid = post_id(row)
        text = str(row.get("text") or row.get("content") or "").strip()
        if not pid or not text or fingerprint(text) in seen:
            continue
        seen.add(fingerprint(text))
        creator = str(row.get("creator_id") or row.get("creator") or "unknown")
        views = number(row, "views", "view_count", "impressions")
        likes = number(row, "likes", "like_count")
        replies = number(row, "replies", "reply_count", "comments")
        shares = number(row, "shares", "share_count")
        engagement = (likes + 2 * replies + 3 * shares) / views if views > 0 else None
        post = {
            "post_id": pid, "creator": str(row.get("creator") or "unknown"),
            "creator_id": creator, "source_url": row.get("source_url") or row.get("source"),
            "format_observed": str(row.get("format") or "unknown"),
            "views": views, "likes": likes, "replies": replies, "shares": shares,
            "engagement_per_view": round(engagement, 6) if engagement is not None else None,
            "earnings_verified": False,
        }
        public_posts.append(post)
        public_groups[creator].append(post)

    public_creator_benchmarks = []
    for creator, posts in public_groups.items():
        scored = [p for p in posts if p["engagement_per_view"] is not None]
        if len(posts) < MIN_PUBLIC_SAMPLES or not scored:
            continue
        public_creator_benchmarks.append({
            "creator": posts[0]["creator"], "creator_id": creator,
            "posts_observed": len(posts),
            "mean_engagement_per_view": round(sum(p["engagement_per_view"] for p in scored) / len(scored), 6),
            "median_views": sorted(p["views"] for p in posts)[len(posts) // 2],
            "evidence": "PUBLIC_ENGAGEMENT_ONLY",
            "earnings_status": "NOT_PUBLICLY_VERIFIED",
            "sample_post_ids": [p["post_id"] for p in posts[:5]],
        })
    public_creator_benchmarks.sort(
        key=lambda p: (p["posts_observed"] >= 5, p["mean_engagement_per_view"], p["posts_observed"]),
        reverse=True,
    )

    attrs = {post_id(x): x for x in read_jsonl(ATTRIBUTION) if post_id(x)}
    perf = {post_id(x): x for x in read_jsonl(PERFORMANCE) if post_id(x)}
    rewards = {}
    rejected_rewards = 0
    raw_rewards = read_jsonl(REWARD_EVENTS)
    for event in raw_rewards:
        if is_verified_reward_event(event):
            rewards[canonical_post_id(event)] = event
        else:
            rejected_rewards += 1

    own_posts = []
    for pid, attr in attrs.items():
        metrics = perf.get(pid, {})
        reward = rewards.get(pid)
        own_posts.append({
            "post_id": pid,
            "category": str(attr.get("content_lane") or attr.get("category") or "unknown"),
            "format": str(attr.get("content_format") or attr.get("format") or "unknown"),
            "hook_type": str(attr.get("hook_type") or attr.get("content_family") or "unknown"),
            "views": number(metrics, "views", "view_count", "impressions"),
            "likes": number(metrics, "likes", "like_count"),
            "replies": number(metrics, "replies", "reply_count", "comments"),
            "shares": number(metrics, "shares", "share_count"),
            "verified_reward_usdc": number(reward, "reward_amount_usdc") if reward else None,
            "reward_evidence": "EXACT_POST_VERIFIED" if reward else "NOT_VERIFIED",
        })

    own_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in own_posts:
        own_groups[(row["category"], row["format"], row["hook_type"])].append(row)
    own_patterns = []
    for (category, fmt, hook), rows in own_groups.items():
        views = sum(x["views"] for x in rows)
        interaction = sum(x["likes"] + 2*x["replies"] + 3*x["shares"] for x in rows)
        reward_rows = [x for x in rows if x["verified_reward_usdc"] is not None]
        own_patterns.append({
            "category": category, "format": fmt, "hook_type": hook,
            "samples": len(rows), "total_views": views,
            "engagement_per_1000_views": round(1000 * interaction / max(views, 1), 4),
            "verified_reward_posts": len(reward_rows),
            "verified_reward_usdc": round(sum(x["verified_reward_usdc"] for x in reward_rows), 8),
            "evidence": "EXACT_POST_REWARD_PLUS_PERFORMANCE" if reward_rows else "OBSERVATIONAL_ONLY",
        })
    own_patterns.sort(key=lambda x: (
        x["verified_reward_posts"] > 0, x["verified_reward_usdc"], x["engagement_per_1000_views"]
    ), reverse=True)

    experiments = []
    for row in own_patterns:
        if row["samples"] >= MIN_OWN_SAMPLES:
            experiments.append({
                "hypothesis": f"Replicate {row['category']} / {row['format']} / {row['hook_type']} only when a fresh, independently validated opportunity exists.",
                "basis": row["evidence"], "sample_count": row["samples"],
                "promotion_rule": "Require at least 3 comparable own posts and verify post-cost forecast quality; engagement or revenue alone does not prove trading skill.",
            })
    if not experiments and public_creator_benchmarks:
        experiments.append({
            "hypothesis": "Test one original editorial structure inspired by public engagement patterns against NIC's own baseline.",
            "basis": "PUBLIC_ENGAGEMENT_ONLY", "sample_count": len(public_posts),
            "promotion_rule": "Treat as a hypothesis; do not claim earnings or copy text, identity, or distinctive phrasing.",
        })

    result = {
        "schema_version": "1.0", "generated_at": now,
        "status": "LEARNING_HYPOTHESES_READY" if public_posts or own_posts else "WAITING_FOR_OBSERVATIONS",
        "purpose": "Autonomous evidence-bounded creator learning; not model-weight training or self-modifying code.",
        "counts": {
            "public_posts_observed": len(public_posts),
            "public_creators_with_minimum_samples": len(public_creator_benchmarks),
            "own_attributed_posts": len(own_posts),
            "verified_exact_post_reward_events": len(rewards),
            "rejected_reward_events": rejected_rewards,
        },
        "public_creator_benchmarks": public_creator_benchmarks[:30],
        "own_post_patterns": own_patterns[:50],
        "next_experiments": experiments[:8],
        "guardrails": {
            "public_views_are_not_earnings": True,
            "public_engagement_is_not_proof_of_500_usd_weekly_income": True,
            "reward_requires_exact_post_and_verified_hashed_timestamped_evidence": True,
            "no_copying_creator_text_or_identity": True,
            "no_automatic_source_code_mutation": True,
            "automatic_publication_authorized": False,
            "trading_authorized": False,
            "forecast_profitability_proven": False,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({
        "generated_at": now, "status": result["status"], "counts": result["counts"],
        "output": str(OUT.relative_to(ROOT)),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "counts": result["counts"], "experiments": len(experiments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
