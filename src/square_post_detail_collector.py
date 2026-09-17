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
POST_METRICS = ROOT / "analytics/post_metrics.jsonl"
STATE = ROOT / "analytics/square_post_detail_state.json"
DETAIL_BASE = "https://www.binance.com/bapi/composite/v3/friendly/pgc/special/content/detail/{post_id}"


def get_json(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; BinanceSquarePostDetailCollector/1.1)",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.binance.com/en/square",
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def publications():
    rows = []
    if not PUB.exists():
        return rows
    for line in PUB.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict): rows.append(row)
        except Exception:
            pass
    return rows


def normalize_id(value):
    s = str(value or "").strip()
    if not s: return ""
    return s.rstrip("/").split("?")[0].split("#")[0].lower()


def post_ids(row):
    ids = []
    for key in ("post_id", "postId", "content_id", "contentId", "publication_id", "publicationId", "square_post_id", "squarePostId", "canonical_post_id"):
        value = normalize_id(row.get(key))
        if value and value not in ids: ids.append(value)
    for key in ("link", "url", "webLink", "shareUrl", "share_url"):
        text = str(row.get(key) or "")
        for found in re.findall(r"/(?:uni-qr/cpos|square/post|post|content)/([A-Za-z0-9_-]+)", text, flags=re.I):
            value = normalize_id(found)
            if value and value not in ids: ids.append(value)
    return ids


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values(): yield from walk(value)
    elif isinstance(node, list):
        for value in node: yield from walk(value)


def metric(node, names):
    if not isinstance(node, dict): return None
    for name in names:
        value = node.get(name)
        if value in (None, ""): continue
        try: return float(value)
        except (TypeError, ValueError): pass
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
            if value is not None: local[name] = value
        if len(local) > len(best): best = local
    return best


def extract_post(payload, post_id):
    metrics = find_metrics(payload)
    for node in walk(payload):
        if not isinstance(node, dict): continue
        candidate_id = normalize_id(node.get("postId") or node.get("post_id") or node.get("contentId") or node.get("content_id") or node.get("id"))
        if candidate_id == post_id: return metrics, node
    return metrics, {}


def learning_seen():
    seen = set()
    if not POST_METRICS.exists(): return seen
    for line in POST_METRICS.read_text(encoding="utf-8").splitlines()[-5000:]:
        try:
            row = json.loads(line)
            if isinstance(row, dict): seen.add(f"{row.get('post_id')}:{str(row.get('collected_at',''))[:13]}")
        except Exception: pass
    return seen


def main():
    state = {}
    if STATE.exists():
        try: state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception: state = {}
    seen = state.get("seen", {}) if isinstance(state.get("seen"), dict) else {}
    learning_ids = learning_seen()
    pubs = publications()
    now = datetime.now(timezone.utc).isoformat()
    checked = matched = written = learning_written = 0
    failures = []
    OUT.parent.mkdir(parents=True, exist_ok=True)

    for pub in pubs[-200:]:
        ids = post_ids(pub)
        if not ids: continue
        post_id = ids[0]; checked += 1
        try:
            payload = get_json(DETAIL_BASE.format(post_id=post_id))
            metrics, _ = extract_post(payload, post_id)
            if not metrics:
                failures.append({"post_id": post_id, "reason": "no_explicit_metrics_returned"}); continue
            matched += 1
            key = f"{post_id}:{now[:13]}"
            if key not in seen:
                record = {"collected_at": now, "post_id": post_id, "canonical_post_id": post_id, "publication_id_aliases": ids, "metrics": metrics, "metric_presence": {k: True for k in metrics}, "symbol": pub.get("symbol"), "category": pub.get("category"), "web_link": pub.get("link"), "source": "Binance Square public post detail", "collector_version": "3.1-post-detail-learning-bridge", "metrics_verified": True}
                with OUT.open("a", encoding="utf-8") as fh: fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                seen[key] = record; written += 1
            if key not in learning_ids:
                learning_record = {
                    "collected_at": now, "post_id": post_id, "symbol": pub.get("symbol"), "category": pub.get("category"),
                    "format": pub.get("format") or pub.get("experiment_format"), "experiment_id": pub.get("experiment_id"),
                    "hook_type": pub.get("hook_type"), "editorial_style": pub.get("editorial_style"), "visual_type": pub.get("visual_type"),
                    "views": metrics.get("views"), "likes": metrics.get("likes"), "replies": metrics.get("comments"),
                    "shares": metrics.get("shares"), "quotes": metrics.get("quotes"), "followers_gained": None,
                    "metrics_verified": True, "source": "Binance Square public post detail", "collector_version": "3.1-post-detail-learning-bridge",
                }
                with POST_METRICS.open("a", encoding="utf-8") as fh: fh.write(json.dumps(learning_record, ensure_ascii=False) + "\n")
                learning_ids.add(key); learning_written += 1
            time.sleep(0.08)
        except Exception as exc:
            failures.append({"post_id": post_id, "reason": f"request_failed:{type(exc).__name__}"})

    if len(seen) > 5000: seen = dict(sorted(seen.items())[-5000:])
    result = {"last_run": now, "published_records": len(pubs), "posts_checked": checked, "posts_with_explicit_metrics": matched, "written": written, "learning_metrics_written": learning_written, "failures": failures[-100:], "collector_version": "3.1-post-detail-learning-bridge", "metrics_fabricated": False, "source": "Binance Square public post detail", "endpoint": DETAIL_BASE.replace("{post_id}", "<post_id>"), "learning_output": str(POST_METRICS), "seen": seen}
    STATE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("published_records", "posts_checked", "posts_with_explicit_metrics", "written", "learning_metrics_written", "collector_version")}, indent=2))


if __name__ == "__main__": main()
