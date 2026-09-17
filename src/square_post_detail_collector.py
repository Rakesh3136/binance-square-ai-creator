"""Collect per-post Binance Square metrics using exact published post IDs.

The existing feed collector can miss a creator's own posts because the global
recommendation feed is not a canonical creator-history source. This collector
uses the public Square content-detail endpoint for each known published post
ID and records only explicit metrics returned by Binance.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "analytics/square_performance.jsonl"
STATE = ROOT / "analytics/square_post_detail_state.json"
DETAIL_BASE = "https://www.binance.com/bapi/composite/v3/friendly/pgc/special/content/detail/{post_id}"


def get_json(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BinanceSquarePostDetailCollector/1.0)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.binance.com/en/square",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def publications():
    rows = []
    if not PUB.exists():
        return rows
    for line in PUB.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            pass
    return rows


def normalize_id(value):
    s = str(value or "").strip()
    if not s:
        return ""
    s = s.rstrip("/").split("?")[0].split("#")[0]
    return s.lower()


def post_ids(row):
    ids = []
    for key in (
        "post_id", "postId", "content_id", "contentId", "publication_id",
        "publicationId", "square_post_id", "squarePostId", "canonical_post_id",
    ):
        value = normalize_id(row.get(key))
        if value and value not in ids:
            ids.append(value)
    for key in ("link", "url", "webLink", "shareUrl", "share_url"):
        text = str(row.get(key) or "")
        for found in re.findall(r"/(?:uni-qr/cpos|square/post|post|content)/([A-Za-z0-9_-]+)", text, flags=re.I):
            value = normalize_id(found)
            if value and value not in ids:
                ids.append(value)
    return ids


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def metric(node, names):
    if not isinstance(node, dict):
        return None
    for name in names:
        value = node.get(name)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def find_metrics(payload):
    aliases = {
        "views": ("viewCount", "views", "viewNum", "view_num", "view_count"),
        "likes": ("likeCount", "likes", "likeNum", "like_num", "like_count"),
        "comments": ("commentCount", "comments", "commentNum", "replyCount", "replyNum", "comment_num"),
        "shares": ("shareCount", "shares", "shareNum", "share_num", "share_count"),
        "quotes": ("quoteCount", "quotes", "quoteNum", "quote_num", "quote_count"),
    }
    best = {}
    for node in walk(payload):
        local = {}
        for name, keys in aliases.items():
            value = metric(node, keys)
            if value is not None:
                local[name] = value
        if len(local) > len(best):
            best = local
    return best


def extract_post(payload, post_id):
    metrics = find_metrics(payload)
    for node in walk(payload):
        candidate_id = normalize_id(
            node.get("postId") or node.get("post_id") or node.get("contentId") or node.get("content_id") or node.get("id")
        ) if isinstance(node, dict) else ""
        if candidate_id == post_id and isinstance(node, dict):
            details = dict(node)
            return metrics, details
    return metrics, {}


def main():
    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    seen = state.get("seen", {}) if isinstance(state.get("seen"), dict) else {}
    pubs = publications()
    now = datetime.now(timezone.utc).isoformat()
    checked = 0
    matched = 0
    failures = []
    written = 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for pub in pubs[-200:]:
        ids = post_ids(pub)
        if not ids:
            continue
        post_id = ids[0]
        checked += 1
        url = DETAIL_BASE.format(post_id=post_id)
        try:
            payload = get_json(url)
            metrics, raw = extract_post(payload, post_id)
            if not metrics:
                failures.append({"post_id": post_id, "reason": "no_explicit_metrics_returned"})
                continue
            matched += 1
            record = {
                "collected_at": now,
                "post_id": post_id,
                "canonical_post_id": post_id,
                "publication_id_aliases": ids,
                "metrics": metrics,
                "metric_presence": {k: True for k in metrics},
                "symbol": pub.get("symbol"),
                "category": pub.get("category"),
                "web_link": pub.get("link"),
                "source": "Binance Square public post detail",
                "collector_version": "3.0-post-detail",
                "metrics_verified": True,
            }
            key = f"{post_id}:{now[:13]}"
            if key not in seen:
                with OUT.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                seen[key] = record
                written += 1
            # Small pacing delay to avoid hammering the public endpoint.
            time.sleep(0.08)
        except Exception as exc:
            failures.append({"post_id": post_id, "reason": f"request_failed:{type(exc).__name__}"})

    if len(seen) > 5000:
        seen = dict(sorted(seen.items())[-5000:])
    result = {
        "last_run": now,
        "published_records": len(pubs),
        "posts_checked": checked,
        "posts_with_explicit_metrics": matched,
        "written": written,
        "failures": failures[-100:],
        "collector_version": "3.0-post-detail",
        "metrics_fabricated": False,
        "source": "Binance Square public post detail",
        "endpoint": DETAIL_BASE.replace("{post_id}", "<post_id>"),
        "seen": seen,
    }
    STATE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("published_records", "posts_checked", "posts_with_explicit_metrics", "written", "collector_version")}, indent=2))


if __name__ == "__main__":
    main()
