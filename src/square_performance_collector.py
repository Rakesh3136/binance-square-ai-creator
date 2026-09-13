import json, os, re, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Binance changes internal Square feed shapes periodically. Keep several public
# read routes and parse recursively instead of assuming one {data:{list:[]}}
# response shape. This collector is read-only and never uses trading/posting keys.
BASES = [
    "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v1/friendly/pgc/content/article/list",
]
OUT = Path("analytics/square_performance.jsonl")
STATE = Path("analytics/square_performance_state.json")
PUB = Path("analytics/publication_log.jsonl")


def get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BinanceSquarePerformanceCollector/2.0)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.binance.com/en/square",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def load(path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def publications():
    rows = []
    if not PUB.exists():
        return rows
    for line in PUB.read_text(encoding="utf-8").splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict):
                rows.append(x)
        except Exception:
            continue
    return rows


def post_id(row):
    if not isinstance(row, dict):
        return ""
    for k in ("post_id", "postId", "id", "content_id", "contentId", "articleId", "publication_id"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    for k in ("link", "url", "webLink", "shareUrl", "share_url"):
        link = str(row.get(k) or "")
        m = re.search(r"(?:post|content|cpos|article)/([A-Za-z0-9_-]+)", link)
        if m:
            return m.group(1)
    return ""


def looks_like_post(obj):
    if not isinstance(obj, dict):
        return False
    pid = post_id(obj)
    # Require an identifier plus at least one content/metric field. This avoids
    # treating pagination metadata or unrelated nested objects as posts.
    fields = set(obj.keys())
    return bool(pid) and bool(fields & {
        "title", "content", "text", "body", "authorName", "author",
        "viewCount", "views", "likeCount", "commentCount", "replyCount",
        "shareCount", "createTime", "publishedAt", "webLink", "url"
    })


def walk_posts(node, found):
    """Recursively collect post-shaped dicts from changing API envelopes."""
    if isinstance(node, dict):
        if looks_like_post(node):
            found[post_id(node)] = node
        for value in node.values():
            walk_posts(value, found)
    elif isinstance(node, list):
        for value in node:
            walk_posts(value, found)


def fetch_recent(max_pages=20, page_size=50):
    found = {}
    attempts = []
    # Internal endpoint parameter names have changed over time; try the common
    # variants while keeping the request count bounded.
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
                try:
                    data = get_json(url)
                except Exception:
                    break
                before = len(base_found)
                walk_posts(data, base_found)
                # A successful envelope with no posts means this parameter
                # variant is not useful; move to the next one.
                if len(base_found) == before and page == 1:
                    break
                # Stop once the response has clearly stopped yielding new rows.
                if page > 1 and len(base_found) == before:
                    break
                time.sleep(0.15)
            if base_found:
                break
        if base_found:
            found.update(base_found)
            break
    return found, attempts


def metric(item, *keys):
    if not isinstance(item, dict):
        return 0.0
    # Also accept nested metric objects used by some Square responses.
    containers = [item]
    for k in ("stats", "statistics", "metrics", "interaction", "engagement"):
        if isinstance(item.get(k), dict):
            containers.append(item[k])
    for container in containers:
        for key in keys:
            v = container.get(key)
            if v is not None and v != "":
                try:
                    return float(v)
                except Exception:
                    continue
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
    pubs = publications()
    recent, attempts = fetch_recent()
    now = datetime.now(timezone.utc).isoformat()
    matches = []
    matched_ids = set()

    # The publication log is authoritative for our own posts. Match by post ID
    # first, then by URL-derived ID; never fabricate performance numbers.
    for pub in pubs:
        pid = post_id(pub)
        if not pid or pid not in recent:
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
            "metrics": metrics,
            "metric_presence": metric_presence(item),
            "author_name": item.get("authorName") or (item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else item.get("authorName"),
            "web_link": item.get("webLink") or item.get("url") or pub.get("link"),
            "card_type": item.get("cardType") or item.get("contentType"),
            "source": "Binance Square public content feed",
            "collector_version": "2.0-resilient",
        })
        matched_ids.add(pid)

    seen = state.get("seen", {}) if isinstance(state.get("seen", {}), dict) else {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT.open("a", encoding="utf-8") as f:
        for r in matches:
            # One observation per post/hour lets the learning engine calculate
            # growth curves instead of treating the latest snapshot as a score.
            key = f"{r['post_id']}:{r['collected_at'][:13]}"
            if key in seen:
                continue
            seen[key] = r
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            written += 1

    # Keep state bounded. Old hourly observations remain in the JSONL history;
    # the state file only needs a recent dedupe window.
    if len(seen) > 5000:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[0])[-5000:])
    STATE.write_text(
        json.dumps({
            "last_run": now,
            "seen": seen,
            "last_match_count": len(matches),
            "last_written_count": written,
            "published_records": len(pubs),
            "feed_records": len(recent),
            "matched_post_ids": len(matched_ids),
            "request_attempts": len(attempts),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "OK",
        "published_records": len(pubs),
        "feed_records": len(recent),
        "matched_post_ids": len(matched_ids),
        "collected": len(matches),
        "written": written,
        "source": "Binance Square public feed",
        "collector_version": "2.0-resilient",
        "output": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
