"""Verified Binance Square performance collector with canonical ID attribution.

The public Square feed has changed shapes over time. This collector therefore
normalizes identifiers from both publication records and feed records, indexes
all trustworthy aliases, and matches by exact canonical ID/URL identity only.
It never fabricates performance metrics or fuzzy-matches posts by text.
"""
from __future__ import annotations
import json, re, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASES = [
    "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v1/friendly/pgc/content/article/list",
]
OUT = Path("analytics/square_performance.jsonl")
STATE = Path("analytics/square_performance_state.json")
PUB = Path("analytics/publication_log.jsonl")


def get_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; BinanceSquarePerformanceCollector/2.1)",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.binance.com/en/square",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def load(path, default):
    if not path.exists(): return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception: return default


def publications():
    rows = []
    if not PUB.exists(): return rows
    for line in PUB.read_text(encoding="utf-8").splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict): rows.append(x)
        except Exception: continue
    return rows


def normalize_id(value):
    """Normalize an ID without destroying meaningful alphanumeric Square IDs."""
    if value is None: return ""
    s = str(value).strip()
    if not s: return ""
    s = s.rstrip("/").split("?")[0].split("#")[0]
    if s.startswith("$SQUARE:"): s = s[8:]
    return s.lower()


def ids_from_url(value):
    url = str(value or "").strip()
    if not url: return []
    found = []
    patterns = (
        r"/(?:square/)?post/([A-Za-z0-9_-]+)",
        r"/(?:square/)?content/([A-Za-z0-9_-]+)",
        r"/(?:square/)?article/([A-Za-z0-9_-]+)",
        r"/(?:square/)?cpos/([A-Za-z0-9_-]+)",
    )
    for pattern in patterns:
        for match in re.findall(pattern, url, flags=re.I):
            value = normalize_id(match)
            if value and value not in found: found.append(value)
    return found


def id_candidates(row):
    """Return all defensible post identifiers; never infer an ID from text."""
    if not isinstance(row, dict): return []
    out = []
    for key in (
        "post_id", "postId", "content_id", "contentId", "articleId",
        "publication_id", "publicationId", "square_post_id", "squarePostId",
        "contentID", "article_id", "article_id_str"
    ):
        value = normalize_id(row.get(key))
        if value and value not in out: out.append(value)
    for key in ("link", "url", "webLink", "shareUrl", "share_url", "web_url"):
        for value in ids_from_url(row.get(key)):
            if value not in out: out.append(value)
    return out


def looks_like_post(obj):
    if not isinstance(obj, dict): return False
    ids = id_candidates(obj)
    fields = set(obj.keys())
    return bool(ids) and bool(fields & {
        "title", "content", "text", "body", "authorName", "author",
        "viewCount", "views", "likeCount", "commentCount", "replyCount",
        "shareCount", "createTime", "publishedAt", "webLink", "url"
    })


def walk_posts(node, found):
    if isinstance(node, dict):
        if looks_like_post(node):
            ids = id_candidates(node)
            for pid in ids:
                found[pid] = node
        for value in node.values(): walk_posts(value, found)
    elif isinstance(node, list):
        for value in node: walk_posts(value, found)


def fetch_recent(max_pages=20, page_size=50):
    found, attempts = {}, []
    page_variants = (
        "pageIndex={page}&pageSize={size}&type=2",
        "pageNo={page}&pageSize={size}&type=2",
        "page={page}&pageSize={size}&type=2",
    )
    for base in BASES:
        base_found = {}
        for template in page_variants:
            for page in range(1, max_pages + 1):
                url = f"{base}?{template.format(page=page, size=page_size)}"
                attempts.append(url)
                try: data = get_json(url)
                except Exception: break
                before = len(base_found); walk_posts(data, base_found)
                if len(base_found) == before and page == 1: break
                if page > 1 and len(base_found) == before: break
                time.sleep(0.15)
            if base_found: break
        if base_found:
            found.update(base_found); break
    return found, attempts


def metric(item, *keys):
    if not isinstance(item, dict): return 0.0
    containers = [item]
    for k in ("stats", "statistics", "metrics", "interaction", "engagement"):
        if isinstance(item.get(k), dict): containers.append(item[k])
    for container in containers:
        for key in keys:
            v = container.get(key)
            if v is not None and v != "":
                try: return float(v)
                except Exception: pass
    return 0.0


def metric_presence(item):
    names = {
        "views": ("viewCount", "views", "view_num", "viewNum"),
        "likes": ("likeCount", "likes", "like_num", "likeNum"),
        "comments": ("commentCount", "comments", "replyCount", "replyNum"),
        "shares": ("shareCount", "shares", "shareNum"),
        "quotes": ("quoteCount", "quotes", "quoteNum"),
    }
    return {name: any(metric(item, key) != 0 for key in keys) for name, keys in names.items()}


def main():
    state = load(STATE, {"last_run": "", "seen": {}})
    pubs = publications(); recent, attempts = fetch_recent()
    now = datetime.now(timezone.utc).isoformat()
    matches, matched_ids = [], set(); unmatched_publications = []

    for pub in pubs:
        candidates = id_candidates(pub)
        pid = next((x for x in candidates if x in recent), "")
        if not pid:
            if candidates: unmatched_publications.append(candidates[0])
            continue
        item = recent[pid]
        metrics = {
            "views": metric(item, "viewCount", "views", "view_num", "viewNum"),
            "likes": metric(item, "likeCount", "likes", "like_num", "likeNum"),
            "comments": metric(item, "commentCount", "comments", "replyCount", "replyNum"),
            "shares": metric(item, "shareCount", "shares", "shareNum"),
            "quotes": metric(item, "quoteCount", "quotes", "quoteNum"),
        }
        matches.append({
            "collected_at": now,
            "post_id": pid,
            "canonical_post_id": pid,
            "publication_id_aliases": candidates,
            "metrics": metrics,
            "metric_presence": metric_presence(item),
            "author_name": item.get("authorName") or ((item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else ""),
            "web_link": item.get("webLink") or item.get("url") or pub.get("link"),
            "card_type": item.get("cardType") or item.get("contentType"),
            "source": "Binance Square public content feed",
            "collector_version": "2.1-canonical-id-attribution",
            "metrics_verified": True,
        })
        matched_ids.add(pid)

    seen = state.get("seen", {}) if isinstance(state.get("seen", {}), dict) else {}
    OUT.parent.mkdir(parents=True, exist_ok=True); written = 0
    for r in matches:
        key = f"{r['canonical_post_id']}:{r['collected_at'][:13]}"
        if key in seen: continue
        seen[key] = r
        with OUT.open("a", encoding="utf-8") as f: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        written += 1
    if len(seen) > 5000: seen = dict(sorted(seen.items(), key=lambda kv: kv[0])[-5000:])

    diagnostics = {
        "last_run": now,
        "seen": seen,
        "last_match_count": len(matches),
        "last_written_count": written,
        "published_records": len(pubs),
        "feed_records": len(recent),
        "matched_post_ids": len(matched_ids),
        "unmatched_publications": len(unmatched_publications),
        "unmatched_with_id": len(unmatched_publications),
        "request_attempts": len(attempts),
        "collector_version": "2.1-canonical-id-attribution",
        "attribution_policy": "exact_normalized_id_or_url_alias_only",
        "fuzzy_text_matching": False,
        "metrics_fabricated": False,
    }
    STATE.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK", "published_records": len(pubs), "feed_records": len(recent),
        "matched_post_ids": len(matched_ids), "collected": len(matches), "written": written,
        "unmatched_publications": len(unmatched_publications),
        "source": "Binance Square public feed", "collector_version": "2.1-canonical-id-attribution",
        "output": str(OUT),
    }, indent=2))


if __name__ == "__main__": main()
