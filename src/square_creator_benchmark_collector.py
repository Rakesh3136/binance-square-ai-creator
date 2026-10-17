"""Collect public Binance Square creator examples for weekly, evidence-bounded benchmarking.

This collector measures public content and visible engagement only. It cannot see
private Write-to-Earn payout dashboards and never labels a creator a $500 earner.
Text is capped to a short excerpt for classification; original posts are linked.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASES = [
    "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v1/friendly/pgc/content/article/list",
]
EXAMPLES = ROOT / "data/intelligence/public_square_examples.json"
OUT = ROOT / "data/intelligence/square_creator_benchmark.json"
REPORT = ROOT / "data/live/square_creator_benchmark_report.json"
STATE = ROOT / "analytics/square_creator_benchmark_state.json"
MAX_PAGES = 6
PAGE_SIZE = 30
MAX_TEXT = 700
MAX_EXAMPLES = 1200


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; NICPublicCreatorBenchmark/1.0)",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.binance.com/en/square",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_id(value: Any) -> str:
    raw = str(value or "").strip().rstrip("/").split("?", 1)[0].split("#", 1)[0]
    return raw.lower()


def text_value(row: dict) -> str:
    for key in ("content", "text", "body", "description", "summary", "title"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            clean = re.sub(r"<[^>]+>", " ", value)
            clean = re.sub(r"https?://\S+", "", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                return clean[:MAX_TEXT]
    return ""


def walk_posts(node: Any, found: dict[str, dict]) -> None:
    if isinstance(node, dict):
        candidates = [
            node.get(k) for k in ("postId", "post_id", "contentId", "content_id", "articleId", "article_id", "id")
        ]
        link = next((node.get(k) for k in ("webLink", "shareUrl", "share_url", "url", "link") if node.get(k)), "")
        match = re.search(r"/(?:square/)?post/([A-Za-z0-9_-]+)", str(link), re.I)
        if match:
            candidates.append(match.group(1))
        pid = next((normalize_id(v) for v in candidates if normalize_id(v)), "")
        text = text_value(node)
        if pid and text and len(text) >= 35:
            found.setdefault(pid, node)
        for value in node.values():
            walk_posts(value, found)
    elif isinstance(node, list):
        for item in node:
            walk_posts(item, found)


def metric(row: dict, *keys: str) -> float:
    containers = [row]
    for key in ("stats", "statistics", "metrics", "interaction", "engagement"):
        if isinstance(row.get(key), dict):
            containers.append(row[key])
    for container in containers:
        for key in keys:
            try:
                value = float(container.get(key))
                if value >= 0:
                    return value
            except (TypeError, ValueError):
                pass
    return 0.0


def post_url(pid: str, row: dict) -> str:
    for key in ("webLink", "shareUrl", "share_url", "url", "link"):
        url = row.get(key)
        if isinstance(url, str) and "/post/" in url and "binance.com" in url:
            return url
    return f"https://www.binance.com/en/square/post/{urllib.parse.quote(pid, safe='')}"


def author(row: dict) -> tuple[str, str]:
    value = row.get("author") if isinstance(row.get("author"), dict) else {}
    name = row.get("authorName") or row.get("nickName") or row.get("nickname") or value.get("name") or value.get("nickName") or ""
    uid = row.get("authorId") or row.get("uid") or value.get("userId") or value.get("id") or ""
    return str(name).strip()[:120], str(uid).strip()[:120]


def fetch_public_posts() -> tuple[list[dict], list[str]]:
    attempts: list[str] = []
    for base in BASES:
        found: dict[str, dict] = {}
        for page_key in ("pageIndex", "pageNo", "page"):
            for page in range(1, MAX_PAGES + 1):
                query = urllib.parse.urlencode({page_key: page, "pageSize": PAGE_SIZE, "type": 2})
                url = f"{base}?{query}"
                attempts.append(url)
                try:
                    payload = fetch_json(url)
                except Exception:
                    break
                before = len(found)
                walk_posts(payload, found)
                if page > 1 and len(found) == before:
                    break
                time.sleep(0.08)
            if found:
                break
        if found:
            break

    observed_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for pid, item in found.items():
        text = text_value(item)
        if not text:
            continue
        name, uid = author(item)
        rows.append({
            "source_type": "public_square_creator_observation",
            "post_id": pid,
            "creator": name or "unknown",
            "creator_id": uid or None,
            "source": post_url(pid, item),
            "source_url": post_url(pid, item),
            "text": text,
            "format": str(item.get("contentType") or item.get("cardType") or "unknown")[:80],
            "views": metric(item, "viewCount", "views", "view_num", "viewNum"),
            "likes": metric(item, "likeCount", "likes", "like_num", "likeNum"),
            "replies": metric(item, "commentCount", "comments", "replyCount", "replyNum", "commentNum"),
            "shares": metric(item, "shareCount", "shares", "shareNum"),
            "followers_gained": 0,
            "observed_at": observed_at,
            "metrics_scope": "public_post_metrics_only",
            "earnings_verified": False,
        })
    return rows, attempts


def engagement_rate(row: dict) -> float | None:
    views = float(row.get("views") or 0)
    if views <= 0:
        return None
    interactions = float(row.get("likes") or 0) + 2 * float(row.get("replies") or 0) + 3 * float(row.get("shares") or 0)
    return interactions / views


def build_benchmark(rows: list[dict], generated_at: str) -> dict:
    by_creator: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        creator = str(row.get("creator_id") or row.get("creator") or "").strip()
        if creator and creator.lower() != "unknown":
            by_creator[creator].append(row)
    leaders = []
    for creator, posts in by_creator.items():
        rates = [engagement_rate(row) for row in posts]
        rates = [rate for rate in rates if rate is not None]
        if len(posts) < 3 or not rates:
            continue
        leaders.append({
            "creator": next((p.get("creator") for p in posts if p.get("creator")), "unknown"),
            "creator_id": creator,
            "observed_posts": len(posts),
            "mean_public_engagement_rate": round(sum(rates) / len(rates), 6),
            "median_public_views": sorted(float(p.get("views") or 0) for p in posts)[len(posts) // 2],
            "evidence": "PUBLIC_ENGAGEMENT_OBSERVATION",
            "earnings_status": "NOT_PUBLICLY_VERIFIED",
            "interpretation": "directional public engagement benchmark only; not a payout or income ranking",
            "sample_urls": [p.get("source_url") for p in posts[:5]],
        })
    leaders.sort(key=lambda row: (row["observed_posts"] >= 5, row["mean_public_engagement_rate"], row["observed_posts"]), reverse=True)
    return {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "status": "PUBLIC_BENCHMARKS_AVAILABLE" if rows else "PUBLIC_FEED_UNAVAILABLE_OR_EMPTY",
        "public_posts_observed": len(rows),
        "distinct_public_creators": len(by_creator),
        "creator_benchmarks": leaders[:50],
        "earnings_policy": {
            "private_weekly_rewards_accessible": False,
            "creator_income_inferred_from_views": False,
            "creator_income_inferred_from_engagement": False,
            "creator_income_inferred_from_self_claims": False,
            "minimum_verified_earnings_records": 0,
            "note": "This collector has no access to private creator reward dashboards. A public engagement benchmark is not evidence that a creator earned $500 or any other amount.",
        },
        "methodology": "Only public post text excerpts, public post metrics, exact URLs and creator identifiers are collected. Require at least three observed posts per creator for a directional benchmark. No copied text is used as a draft.",
        "top_benchmark_ids": [row["creator_id"] for row in leaders[:20]],
    }


def main() -> int:
    existing = read_json(EXAMPLES, [])
    if not isinstance(existing, list):
        existing = []
    public_rows, attempts = fetch_public_posts()
    generated_at = datetime.now(timezone.utc).isoformat()
    by_id = {}
    for row in existing:
        if not isinstance(row, dict):
            continue
        key = normalize_id(row.get("post_id") or row.get("source_url") or row.get("source"))
        if key:
            by_id[key] = row
    for row in public_rows:
        key = normalize_id(row.get("post_id"))
        if key:
            by_id[key] = row
    combined = list(by_id.values())[-MAX_EXAMPLES:]
    benchmark = build_benchmark(public_rows, generated_at)
    benchmark["source_attempt_count"] = len(attempts)
    benchmark["public_posts_collected_this_run"] = len(public_rows)
    write_json(EXAMPLES, combined)
    write_json(OUT, benchmark)
    write_json(REPORT, {
        "generated_at": generated_at,
        "status": benchmark["status"],
        "public_posts_observed": len(public_rows),
        "distinct_public_creators": benchmark["distinct_public_creators"],
        "creator_benchmarks_with_minimum_samples": len(benchmark["creator_benchmarks"]),
        "earnings_claims_verified": 0,
        "earnings_inferred": False,
        "examples_file": str(EXAMPLES.relative_to(ROOT)) if EXAMPLES.is_relative_to(ROOT) else str(EXAMPLES),
        "benchmark_file": str(OUT.relative_to(ROOT)) if OUT.is_relative_to(ROOT) else str(OUT),
    })
    state = read_json(STATE, {})
    state.update({"last_run": generated_at, "last_public_posts": len(public_rows), "last_status": benchmark["status"], "seen_post_count": len(combined)})
    write_json(STATE, state)
    print(json.dumps({"status": benchmark["status"], "public_posts_observed": len(public_rows), "distinct_public_creators": benchmark["distinct_public_creators"], "benchmarks": len(benchmark["creator_benchmarks"]), "earnings_claims_verified": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
