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
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASES = [
    "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/article/list",
    "https://www.binance.com/bapi/composite/v1/friendly/pgc/content/article/list",
]
NEWS_FEED = "https://www.binance.com/bapi/composite/v4/friendly/pgc/feed/news/list"
USER_PROFILE_URL = "https://www.binance.com/bapi/composite/v3/friendly/pgc/user/client"
USER_POSTS_URL = "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/queryUserProfilePageContentsWithFilter"
EXAMPLES = ROOT / "data/intelligence/public_square_examples.json"
OUT = ROOT / "data/intelligence/square_creator_benchmark.json"
REPORT = ROOT / "data/live/square_creator_benchmark_report.json"
STATE = ROOT / "analytics/square_creator_benchmark_state.json"
HISTORY = ROOT / "analytics/square_creator_benchmark_history.jsonl"
MAX_PAGES = 50  # Current public latest feed is typically limited to about 50 pages.
NEWS_MAX_PAGES = 80  # Supplementary news feed supports deeper public pagination.
TRENDING_MAX_PAGES = 9
PAGE_SIZE = 20  # Current public API docs cap pageSize at 20.
REQUEST_DELAY_SECONDS = 0.5
PROFILE_STUDY_CREATORS = 10
PROFILE_MAX_PAGES = 8
PROFILE_HISTORY_DAYS = 14
PROFILE_HISTORY_STATS = {}
MAX_TEXT = 700
MAX_EXAMPLES = 8000
MAX_HISTORY_SNAPSHOTS = 25000
HISTORY_DAYS = 21


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
    for key in ("bodyTextOnly", "content", "text", "body", "description", "summary", "title", "subTitle"):
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


def posted_at(row: dict) -> str | None:
    """Normalize publication time from varied public-feed shapes; never guess unknown dates."""
    priority = ("publishTime", "publishedAt", "published_at", "publish_time", "publishedTime",
                "createTime", "createdAt", "created_at", "createdTime", "create_time",
                "releaseTime", "release_time", "firstReleaseTime", "postTime", "post_time", "createDate",
                "createdDate", "publishDate", "publish_date", "createdTimestamp",
                "createTimestamp", "timestamp", "date")
    candidates = []
    def visit(node, depth=0):
        if depth > 5: return
        if isinstance(node, dict):
            for key in priority:
                value = node.get(key)
                if value not in (None, ""): candidates.append((priority.index(key), value))
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    visit(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:30]:
                if isinstance(value, (dict, list)): visit(value, depth + 1)
    visit(row)
    candidates.sort(key=lambda item: item[0])
    for _, value in candidates:
        try:
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
                stamp = float(value)
                if stamp > 1e12: stamp /= 1000.0
                if 946684800 <= stamp <= 4102444800:
                    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            if parsed.tzinfo is not None and 2000 <= parsed.year <= 2100:
                return parsed.astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError, OverflowError, OSError):
            continue
    return None

def archetype(text: str) -> str:
    t = text.lower()
    families = {
        "breaking_news": ("breaking", "just announced", "etf", "regulation", "headline"),
        "technical_chart": ("breakout", "retest", "support", "resistance", "chart", "candles"),
        "onchain_data": ("on-chain", "onchain", "whale", "open interest", "liquidation", "exchange flow"),
        "education_explainer": ("explained", "how to", "guide", "what is", "means", "beginner"),
        "macro_cross_asset": ("cpi", "inflation", "federal reserve", "fomc", "treasury", "dollar", "rates"),
        "market_movers": ("gainer", "loser", "surge", "volume spike", "outperform"),
        "opinion_debate": ("bullish", "bearish", "agree", "disagree", "which", "would you"),
        "project_research": ("protocol", "tokenomics", "unlock", "revenue", "roadmap", "ecosystem"),
    }
    scored = [(sum(1 for phrase in phrases if phrase in t), name) for name, phrases in families.items()]
    score, name = max(scored, default=(0, "general"))
    return name if score else "general"

def author(row: dict) -> tuple[str, str, str]:
    value = row.get("author") if isinstance(row.get("author"), dict) else {}
    name = (row.get("displayName") or row.get("authorName") or row.get("nickName") or row.get("nickname")
            or value.get("displayName") or value.get("name") or value.get("nickName") or "")
    uid = (row.get("squareUid") or row.get("squareAuthorId") or row.get("authorId") or row.get("uid")
           or value.get("squareUid") or value.get("squareAuthorId") or value.get("userId") or value.get("id") or "")
    username = row.get("username") or row.get("authorUsername") or value.get("username") or ""
    return str(name).strip()[:120], str(uid).strip()[:160], str(username).strip()[:120]


def fetch_json_post(url: str, payload: dict) -> Any:
    """Best-effort public profile lookup; failure is recorded rather than fatal."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; NICPublicCreatorBenchmark/1.0)",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Referer": "https://www.binance.com/en/square",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _payload_data(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False:
        return None
    code = str(payload.get("code") or "")
    if code and code not in {"000000", "0"}:
        return None
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else None


def _resolve_square_uid(username: str, attempts: list[str]) -> str:
    username = str(username or "").strip()
    if not username:
        return ""
    attempts.append(USER_PROFILE_URL + "?username=<redacted>")
    try:
        payload = fetch_json_post(USER_PROFILE_URL, {
            "username": username,
            "getFollowCount": True,
            "queryFollowersInfo": True,
            "queryRelationTokens": True,
        })
        data = _payload_data(payload)
        if not data:
            return ""
        return str(data.get("squareUid") or data.get("squareAuthorId") or "").strip()
    except Exception:
        return ""


def _creator_history_candidates(public_rows: list[dict], limit: int) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in public_rows:
        square_uid = str(row.get("square_uid") or "").strip()
        if square_uid:
            groups[square_uid].append(row)
    if not groups:
        return []

    def score(rows: list[dict], kind: str) -> float:
        views = sum(float(row.get("views") or 0) for row in rows)
        likes = sum(float(row.get("likes") or 0) for row in rows)
        replies = sum(float(row.get("replies") or 0) for row in rows)
        shares = sum(float(row.get("shares") or 0) for row in rows)
        rate = (likes + 2 * replies + 3 * shares) / max(views, 1)
        if kind == "reach":
            return views
        if kind == "discussion":
            return (replies * 2 + shares * 3) / max(views, 1)
        return rate

    chosen: list[str] = []
    for kind in ("engagement", "reach", "discussion"):
        ordered = sorted(groups.items(), key=lambda item: score(item[1], kind), reverse=True)
        for uid, rows in ordered:
            if uid not in chosen:
                chosen.append(uid)
            if len(chosen) >= limit:
                break
        if len(chosen) >= limit:
            break

    result = []
    for uid in chosen:
        rows = groups[uid]
        rows = sorted(rows, key=lambda row: float(row.get("views") or 0), reverse=True)
        sample = rows[0]
        result.append({
            "square_uid": uid,
            "creator": str(sample.get("creator") or "unknown"),
            "creator_username": str(sample.get("creator_username") or ""),
            "feed_posts_observed": len(rows),
        })
    return result


def fetch_creator_profile_history(public_rows: list[dict], attempts: list[str],
                                  now: datetime | None = None) -> list[dict]:
    """Backfill public posts from selected creator profiles for a true 14-day sample.

    Public profile history is best effort: if the endpoint is unavailable or a
    Square UID cannot be resolved, the gap remains explicit. Public posts and
    counters are never considered proof of creator earnings.
    """
    global PROFILE_HISTORY_STATS
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    cutoff = now - timedelta(days=PROFILE_HISTORY_DAYS)
    candidates = _creator_history_candidates(public_rows, PROFILE_STUDY_CREATORS)
    stats = {
        "status": "PROFILE_HISTORY_NOT_AVAILABLE",
        "candidate_creators": len(candidates),
        "profiles_attempted": 0,
        "profiles_resolved": 0,
        "profile_pages_read": 0,
        "profile_posts_collected": 0,
        "profiles_without_older_posts": 0,
        "profile_failures": 0,
        "window_days": PROFILE_HISTORY_DAYS,
        "source": "public_creator_profile_posts",
        "earnings_status": "PUBLIC_METRICS_ONLY_NOT_EARNINGS",
    }
    feed_ids = {normalize_id(row.get("post_id")) for row in public_rows}
    result = []
    for candidate in candidates:
        square_uid = str(candidate.get("square_uid") or "").strip()
        if not square_uid:
            square_uid = _resolve_square_uid(str(candidate.get("creator_username") or ""), attempts)
        if not square_uid:
            stats["profile_failures"] += 1
            continue
        stats["profiles_attempted"] += 1
        cursor = int(now.timestamp() * 1000)
        seen_ids: set[str] = set()
        collected_for_creator = 0
        older_found = False
        for _ in range(PROFILE_MAX_PAGES):
            query = urllib.parse.urlencode({
                "targetSquareUid": square_uid,
                "timeOffset": cursor,
                "filterType": "ALL",
            })
            url = f"{USER_POSTS_URL}?{query}"
            attempts.append(url)
            try:
                payload = fetch_json(url)
            except Exception:
                stats["profile_failures"] += 1
                break
            data = _payload_data(payload)
            if not data:
                stats["profile_failures"] += 1
                break
            contents = data.get("contents")
            if not isinstance(contents, list) or not contents:
                stats["profiles_without_older_posts"] += 1
                break
            stats["profiles_resolved"] += 1 if stats["profiles_resolved"] < stats["profiles_attempted"] else 0
            stats["profile_pages_read"] += 1
            page_new = 0
            stamps = []
            for item in contents:
                if not isinstance(item, dict):
                    continue
                post_id = normalize_id(item.get("id") or item.get("postId") or item.get("contentId") or item.get("content_id"))
                link = next((item.get(k) for k in ("webLink", "shareLink", "shareUrl", "url") if item.get(k)), "")
                match = re.search(r"/(?:square/)?post/([A-Za-z0-9_-]+)", str(link), re.I)
                if not post_id and match:
                    post_id = normalize_id(match.group(1))
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                stamp_text = posted_at(item)
                stamp = aware_datetime(stamp_text) if stamp_text else None
                if stamp:
                    stamps.append(stamp)
                if not stamp or stamp < cutoff or stamp > now + timedelta(minutes=15):
                    if stamp and stamp < cutoff:
                        older_found = True
                    continue
                text = text_value(item)
                if len(text) < 20:
                    continue
                name, uid, username = author(item)
                rows_uid = uid or square_uid
                normalized = {
                    "source_type": "public_square_creator_profile_observation",
                    "post_id": post_id,
                    "creator": name or str(candidate.get("creator") or "unknown"),
                    "creator_id": rows_uid,
                    "square_uid": square_uid,
                    "creator_username": username or str(candidate.get("creator_username") or ""),
                    "source": post_url(post_id, item),
                    "source_url": post_url(post_id, item),
                    "text": text,
                    "posted_at": stamp.isoformat(),
                    "archetype": archetype(text),
                    "format": str(item.get("contentType") or item.get("cardType") or "unknown")[:80],
                    "views": metric(item, "viewCount", "views", "view_num", "viewNum"),
                    "likes": metric(item, "likeCount", "likes", "like_num", "likeNum"),
                    "replies": metric(item, "commentCount", "comments", "replyCount", "replyNum", "commentNum"),
                    "shares": metric(item, "shareCount", "shares", "shareNum"),
                    "followers_gained": 0,
                    "observed_at": now.isoformat(),
                    "metrics_scope": "public_post_metrics_only",
                    "earnings_status": "NOT_PUBLICLY_VERIFIED",
                    "collection_feed": "creator_profile_history",
                    "collection_feeds": ["creator_profile_history"],
                }
                result.append(normalized)
                feed_ids.add(post_id)
                page_new += 1
                collected_for_creator += 1
            if older_found:
                break
            if page_new == 0:
                break
            next_cursor = data.get("timeOffset")
            try:
                next_cursor = int(next_cursor)
            except (TypeError, ValueError):
                next_cursor = None
            if not next_cursor or next_cursor == cursor:
                older_stamps = [int(stamp.timestamp() * 1000) for stamp in stamps if stamp <= now]
                if older_stamps:
                    inferred_cursor = min(older_stamps)
                    if inferred_cursor < cursor:
                        next_cursor = inferred_cursor
                    else:
                        break
                else:
                    break
            cursor = next_cursor
            time.sleep(REQUEST_DELAY_SECONDS)
            if collected_for_creator >= 100:
                break
    stats["profile_posts_collected"] = len(result)
    stats["creators_with_profile_posts"] = len({row["square_uid"] for row in result})
    if result:
        stats["status"] = "PROFILE_HISTORY_COLLECTED"
    elif stats["profile_failures"]:
        stats["status"] = "PROFILE_HISTORY_ENDPOINT_UNAVAILABLE_OR_UIDS_MISSING"
    else:
        stats["status"] = "NO_ADDITIONAL_PROFILE_HISTORY"
    PROFILE_HISTORY_STATS = stats
    return result


def aware_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _collect_feed(base: str, fixed_params: dict, source_name: str,
                  max_pages: int, attempts: list[str]) -> dict[str, dict]:
    """Read one public feed with conservative pagination and empty-page stopping."""
    for page_key in ("pageIndex", "pageNo", "page"):
        local: dict[str, dict] = {}
        consecutive_empty = 0
        page_one_failed_or_empty = False
        for page in range(1, max_pages + 1):
            params = {page_key: page, "pageSize": PAGE_SIZE, **fixed_params}
            url = f"{base}?{urllib.parse.urlencode(params)}"
            attempts.append(url)
            try:
                payload = fetch_json(url)
            except Exception:
                if page == 1:
                    page_one_failed_or_empty = True
                break
            before = len(local)
            walk_posts(payload, local)
            new_count = len(local) - before
            if new_count <= 0:
                consecutive_empty += 1
                if page == 1:
                    page_one_failed_or_empty = True
                    break
                if consecutive_empty >= 3:
                    break
            else:
                consecutive_empty = 0
            time.sleep(REQUEST_DELAY_SECONDS)
        if local:
            for item in local.values():
                item["_nic_collection_feed"] = source_name
            return local
        if not page_one_failed_or_empty:
            break
    return {}


def _merge_feed_rows(found: dict[str, dict], incoming: dict[str, dict], source_name: str) -> None:
    """Merge duplicate public post IDs, preserving richer visible metrics."""
    for pid, item in incoming.items():
        if pid not in found:
            found[pid] = item
            found[pid]["_nic_collection_feeds"] = [source_name]
            continue
        old = found[pid]
        sources = list(old.get("_nic_collection_feeds") or [str(old.get("_nic_collection_feed") or "unknown")])
        if source_name not in sources:
            sources.append(source_name)
        old_score = sum(metric(old, *keys) for keys in (
            ("viewCount", "views", "view_num", "viewNum"),
            ("likeCount", "likes", "like_num", "likeNum"),
            ("commentCount", "comments", "replyCount", "replyNum", "commentNum"),
            ("shareCount", "shares", "shareNum"),
        ))
        new_score = sum(metric(item, *keys) for keys in (
            ("viewCount", "views", "view_num", "viewNum"),
            ("likeCount", "likes", "like_num", "likeNum"),
            ("commentCount", "comments", "replyCount", "replyNum", "commentNum"),
            ("shareCount", "shares", "shareNum"),
        ))
        preferred, other = (item, old) if new_score > old_score else (old, item)
        merged = dict(other)
        merged.update({key: value for key, value in preferred.items() if value not in (None, "", {}, [])})
        merged["_nic_collection_feed"] = str(old.get("_nic_collection_feed") or source_name)
        merged["_nic_collection_feeds"] = sources
        found[pid] = merged


def fetch_public_posts() -> tuple[list[dict], list[str]]:
    attempts: list[str] = []
    found: dict[str, dict] = {}

    # Latest chronological content supplies the primary recent sample. Older
    # API versions are fallbacks only, avoiding redundant scans when v3 works.
    latest: dict[str, dict] = {}
    for base in BASES:
        latest = _collect_feed(base, {"type": 2}, "latest", MAX_PAGES, attempts)
        if latest:
            break
    _merge_feed_rows(found, latest, "latest")

    # Broaden the sample with a trending cohort and a separate news-feed endpoint.
    # These feeds are deduped by post ID; public counters are not payout proof.
    trending = _collect_feed(BASES[0], {"type": 1}, "trending", TRENDING_MAX_PAGES, attempts)
    _merge_feed_rows(found, trending, "trending")
    news = _collect_feed(NEWS_FEED, {}, "news", NEWS_MAX_PAGES, attempts)
    _merge_feed_rows(found, news, "news")

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
            "posted_at": posted_at(item),
            "archetype": archetype(text),
            "format": str(item.get("contentType") or item.get("cardType") or "unknown")[:80],
            "views": metric(item, "viewCount", "views", "view_num", "viewNum"),
            "likes": metric(item, "likeCount", "likes", "like_num", "likeNum"),
            "replies": metric(item, "commentCount", "comments", "replyCount", "replyNum", "commentNum"),
            "shares": metric(item, "shareCount", "shares", "shareNum"),
            "followers_gained": 0,
            "observed_at": observed_at,
            "metrics_scope": "public_post_metrics_only",
            "earnings_status": "NOT_PUBLICLY_VERIFIED",
            "collection_feed": str(item.get("_nic_collection_feed") or "unknown"),
            "collection_feeds": list(item.get("_nic_collection_feeds") or [str(item.get("_nic_collection_feed") or "unknown")]),
        })
    return rows, attempts


def engagement_rate(row: dict) -> float | None:
    views = float(row.get("views") or 0)
    if views <= 0:
        return None
    interactions = float(row.get("likes") or 0) + 2 * float(row.get("replies") or 0) + 3 * float(row.get("shares") or 0)
    return interactions / views


def read_jsonl(path: Path) -> list[dict]:
    result = []
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                result.append(row)
        except json.JSONDecodeError:
            continue
    return result


def update_metric_history(existing: list[dict], public_rows: list[dict], observed_at: str) -> list[dict]:
    """Keep one latest public metric snapshot per post per UTC day for trend analysis."""
    now = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    day = now.date().isoformat()
    cutoff = now - timedelta(days=HISTORY_DAYS)
    keyed: dict[tuple[str, str], dict] = {}

    for row in existing:
        if not isinstance(row, dict):
            continue
        post_id = normalize_id(row.get("post_id"))
        date = str(row.get("observation_date") or "")[:10]
        if not post_id or not date:
            continue
        try:
            stamp = datetime.fromisoformat(str(row.get("observed_at") or date).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if stamp.astimezone(timezone.utc) < cutoff:
                continue
        except (ValueError, TypeError):
            continue
        keyed[(date, post_id)] = row

    for row in public_rows:
        post_id = normalize_id(row.get("post_id") or row.get("source_url"))
        if not post_id:
            continue
        keyed[(day, post_id)] = {
            "observation_date": day,
            "observed_at": now.isoformat(),
            "post_id": post_id,
            "creator": str(row.get("creator") or "unknown")[:120],
            "creator_id": row.get("creator_id"),
            "source_url": row.get("source_url") or row.get("source"),
            "posted_at": row.get("posted_at"),
            "archetype": row.get("archetype") or archetype(str(row.get("text") or "")),
            "format": str(row.get("format") or "unknown")[:80],
            "views": float(row.get("views") or 0),
            "likes": float(row.get("likes") or 0),
            "replies": float(row.get("replies") or 0),
            "shares": float(row.get("shares") or 0),
            "metrics_scope": "public_post_metrics_only",
            "earnings_status": "NOT_PUBLICLY_VERIFIED",
        }

    result = sorted(keyed.values(), key=lambda row: (str(row.get("observation_date") or ""), str(row.get("post_id") or "")))
    return result[-MAX_HISTORY_SNAPSHOTS:]


def _snapshot_trajectory(history: list[dict], days: int, generated_at: str) -> dict:
    now = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    by_post: dict[str, list[dict]] = defaultdict(list)
    for row in history:
        try:
            stamp = datetime.fromisoformat(str(row.get("observed_at") or "").replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                continue
            age = (now - stamp.astimezone(timezone.utc)).total_seconds() / 86400
            if 0 <= age <= days:
                post_id = str(row.get("post_id") or "").strip()
                if post_id:
                    by_post[post_id].append(row)
        except (ValueError, TypeError):
            continue

    deltas = []
    for post_id, snapshots in by_post.items():
        snapshots.sort(key=lambda row: str(row.get("observed_at") or ""))
        if len(snapshots) < 2:
            continue
        first, last = snapshots[0], snapshots[-1]
        deltas.append({
            "post_id": post_id,
            "creator": str(last.get("creator") or first.get("creator") or "unknown"),
            "archetype": str(last.get("archetype") or first.get("archetype") or "general"),
            "observations": len(snapshots),
            "views_delta": float(last.get("views") or 0) - float(first.get("views") or 0),
            "likes_delta": float(last.get("likes") or 0) - float(first.get("likes") or 0),
            "replies_delta": float(last.get("replies") or 0) - float(first.get("replies") or 0),
            "shares_delta": float(last.get("shares") or 0) - float(first.get("shares") or 0),
        })

    def group_summary(key_name: str) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in deltas:
            key = str(row.get(key_name) or "unknown").strip()
            if key and key.lower() != "unknown":
                groups[key].append(row)
        result = []
        for key, items in groups.items():
            if len(items) < 3:
                continue
            n = len(items)
            result.append({
                key_name: key,
                "posts_with_repeat_observations": n,
                "avg_views_growth": round(sum(x["views_delta"] for x in items) / n, 2),
                "avg_likes_growth": round(sum(x["likes_delta"] for x in items) / n, 2),
                "avg_replies_growth": round(sum(x["replies_delta"] for x in items) / n, 2),
                "avg_shares_growth": round(sum(x["shares_delta"] for x in items) / n, 2),
                "evidence": "OBSERVED_METRIC_CHANGE_NOT_REVENUE",
            })
        result.sort(key=lambda x: (x["avg_replies_growth"] + x["avg_shares_growth"], x["avg_views_growth"], x["posts_with_repeat_observations"]), reverse=True)
        return result[:10]

    return {
        "window_days": days,
        "posts_seen": len(by_post),
        "posts_with_repeat_observations": len(deltas),
        "by_creator": group_summary("creator"),
        "by_archetype": group_summary("archetype"),
        "earnings_status": "PUBLIC_METRIC_TRAJECTORY_NOT_EARNINGS",
    }


def build_benchmark(rows: list[dict], generated_at: str, metric_history: list[dict] | None = None) -> dict:
    generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    if generated.tzinfo is None: generated = generated.replace(tzinfo=timezone.utc)
    generated = generated.astimezone(timezone.utc)
    metric_history = metric_history or []
    dated = []
    for row in rows:
        try:
            raw = row.get("posted_at")
            if not raw: continue
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if stamp.tzinfo is None: continue
            age = (generated - stamp.astimezone(timezone.utc)).total_seconds() / 86400
            if age >= -0.25: dated.append((row, age))
        except (ValueError, TypeError): continue
    def window_summary(days):
        selected = [row for row, age in dated if age <= days]
        creator_groups, family_groups = defaultdict(list), defaultdict(list)
        for row in selected:
            key = str(row.get("creator_id") or row.get("creator") or "").strip()
            if key and key.lower() != "unknown": creator_groups[key].append(row)
            family_groups[str(row.get("archetype") or archetype(str(row.get("text") or "")))].append(row)
        creators = []
        for key, posts in creator_groups.items():
            rates = [engagement_rate(p) for p in posts]; rates = [x for x in rates if x is not None]
            if len(posts) < 3 or not rates: continue
            total_views = sum(float(p.get("views") or 0) for p in posts)
            total_replies = sum(float(p.get("replies") or 0) for p in posts)
            total_shares = sum(float(p.get("shares") or 0) for p in posts)
            by_type = defaultdict(int)
            for p in posts:
                by_type[str(p.get("archetype") or archetype(str(p.get("text") or "")))] += 1
            creators.append({
                "creator": next((p.get("creator") for p in posts if p.get("creator")), "unknown"),
                "creator_id": key, "posts": len(posts),
                "mean_public_engagement_rate": round(sum(rates)/len(rates), 6),
                "median_views": sorted(float(p.get("views") or 0) for p in posts)[len(posts)//2],
                "avg_views": round(total_views/len(posts), 2),
                "reply_rate": round(total_replies/max(1,total_views), 6),
                "share_rate": round(total_shares/max(1,total_views), 6),
                "dominant_archetypes": [name for name, _ in sorted(by_type.items(), key=lambda item: item[1], reverse=True)[:3]],
                "sample_urls": [p.get("source_url") for p in posts[:5]],
                "earnings_status": "NOT_PUBLICLY_VERIFIED"
            })
        creators.sort(key=lambda x: (x["mean_public_engagement_rate"], x["posts"], x["reply_rate"]), reverse=True)
        creators_by_reach = sorted(creators, key=lambda x: (x["median_views"], x["avg_views"], x["posts"]), reverse=True)
        creators_by_discussion = sorted(creators, key=lambda x: (x["reply_rate"], x["share_rate"], x["posts"]), reverse=True)
        families = []
        for name, posts in family_groups.items():
            rates = [engagement_rate(p) for p in posts]; rates = [x for x in rates if x is not None]
            if len(posts) < 3 or not rates: continue
            families.append({"archetype": name, "samples": len(posts), "mean_public_engagement_rate": round(sum(rates)/len(rates), 6), "avg_views": round(sum(float(p.get("views") or 0) for p in posts)/len(posts), 2), "avg_replies": round(sum(float(p.get("replies") or 0) for p in posts)/len(posts), 2), "confidence": "medium" if len(posts) >= 10 else "tentative"})
        families.sort(key=lambda x: (x["mean_public_engagement_rate"], x["samples"]), reverse=True)
        prior_week = [row for row, age in dated if age <= 7]
        older_week = [row for row, age in dated if 7 < age <= 14]
        return {
            "window_days": days,
            "dated_posts": len(selected),
            "distinct_creators": len(creator_groups),
            "creator_candidates": creators[:20],
            "top_by_public_engagement": creators[:10],
            "top_by_median_reach": creators_by_reach[:10],
            "top_by_discussion_and_shares": creators_by_discussion[:10],
            "performance_by_archetype": families[:12],
            "coverage": {
                "posts_age_0_to_7_days": len(prior_week),
                "posts_age_8_to_14_days": len(older_week),
                "older_window_has_distinct_samples": bool(older_week),
                "status": "SUFFICIENT_DATE_SPREAD" if days == 7 or older_week else "NO_DISTINCT_POSTS_IN_DAYS_8_TO_14",
            },
            "metric_trajectory": _snapshot_trajectory(metric_history, days, generated_at),
            "earnings_status": "PUBLIC_METRICS_ONLY_NOT_EARNINGS"
        }
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
        "rolling_learning_windows": {"seven_day": window_summary(7), "fourteen_day": window_summary(14)},
        "creator_archetypes": sorted({str(row.get("archetype") or archetype(str(row.get("text") or ""))) for row in rows}),
        "research_policy": {"rolling_windows_days": [7, 14], "unknown_dates_excluded_from_windows": True, "public_metrics_are_not_earnings": True, "minimum_posts_per_creator_or_archetype": 3, "copying_post_text_forbidden": True},
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
        if not key:
            key = "legacy:" + hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        by_id[key] = row
    for row in public_rows:
        key = normalize_id(row.get("post_id"))
        if key:
            by_id[key] = row
    combined = list(by_id.values())[-MAX_EXAMPLES:]
    metric_history = update_metric_history(read_jsonl(HISTORY), public_rows, generated_at)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in metric_history), encoding="utf-8")
    benchmark = build_benchmark(combined, generated_at, metric_history)
    benchmark["metric_history"] = {
        "path": "analytics/square_creator_benchmark_history.jsonl",
        "observations_retained": len(metric_history),
        "retention_days": HISTORY_DAYS,
        "one_snapshot_per_post_per_utc_day": True,
    }
    benchmark["source_attempt_count"] = len(attempts)
    benchmark["public_posts_collected_this_run"] = len(public_rows)
    benchmark["collection_feed_counts"] = dict(sorted(Counter(str(row.get("collection_feed") or "unknown") for row in public_rows).items()))
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
        "source_attempt_count": len(attempts),
        "collection_feed_counts": benchmark["collection_feed_counts"],
        "examples_file": str(EXAMPLES.relative_to(ROOT)) if EXAMPLES.is_relative_to(ROOT) else str(EXAMPLES),
        "benchmark_file": str(OUT.relative_to(ROOT)) if OUT.is_relative_to(ROOT) else str(OUT),
    })
    state = read_json(STATE, {})
    state.update({"last_run": generated_at, "last_public_posts": len(public_rows), "last_status": benchmark["status"], "seen_post_count": len(combined), "metric_history_rows": len(metric_history), "history_retention_days": HISTORY_DAYS})
    write_json(STATE, state)
    print(json.dumps({"status": benchmark["status"], "public_posts_observed": len(public_rows), "distinct_public_creators": benchmark["distinct_public_creators"], "benchmarks": len(benchmark["creator_benchmarks"]), "collection_feed_counts": benchmark["collection_feed_counts"], "earnings_claims_verified": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
