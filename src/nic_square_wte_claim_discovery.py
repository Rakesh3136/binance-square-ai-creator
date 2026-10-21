"""Discover public Write-to-Earn reward claims from first-party Square hashtag pages.

This is unauthenticated public-claim discovery, not a private earnings scraper.
Creator-reported amounts remain unverified. No session cookies, API keys, browser
fingerprint replay, publishing, likes, follows, or comments are used.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from src.nic_square_earnings_learning import analyze_public_reward_claims
    from src.nic_square_profile_research import (
        BASE, POST_DETAIL_API, _body_text, _data_payload, _dicts, _first_value,
        _parse_profile_post, _user_object, public_json_request,
    )
    from src.square_creator_benchmark_collector import (
        EXAMPLES, author, creator_profile_url, normalize_id, posted_at,
    )
except ModuleNotFoundError:
    from nic_square_earnings_learning import analyze_public_reward_claims
    from nic_square_profile_research import (
        BASE, POST_DETAIL_API, _body_text, _data_payload, _dicts, _first_value,
        _parse_profile_post, _user_object, public_json_request,
    )
    from square_creator_benchmark_collector import (
        EXAMPLES, author, creator_profile_url, normalize_id, posted_at,
    )

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/intelligence/public_wte_claim_discoveries.json"
HASHTAG_SLUGS = ("writetoearn", "write2earn", "binancew2e", "cryptocreators")
MAX_IDS_PER_HASHTAG = 20
MAX_POST_DETAILS_PER_RUN = 60
REQUEST_DELAY_SECONDS = 0.25
MAX_EXAMPLES = 8000
WTE_CONTEXT = re.compile(
    r"write\s*[- ]?to\s*[- ]?earn|write2earn|\bw2e\b|"
    r"creator\s+rewards?|weekly\s+(?:rewards?|earnings?)",
    re.I,
)
AMOUNT_CONTEXT = re.compile(
    r"(?:\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s*(?:USDC|USDT|USD)\b)",
    re.I,
)
CLAIM_ACTION = re.compile(
    r"\b(?:i|we|my|our)\s+(?:earned|made|received|got\s+paid|was\s+paid|"
    r"reward\w*|payout\w*)\b|\b(?:payout|reward(?:ed|s)?|commission(?:s)?|"
    r"bonus(?:es)?)\b.{0,50}(?:\$\s?\d|\d[\d,]*(?:\.\d+)?\s*(?:USDC|USDT|USD))",
    re.I,
)
WTE_HASHTAG_SLUGS = {"writetoearn", "write2earn", "binancew2e"}
POST_ID_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?binance\.com)?/(?:[a-z]{2}(?:-[A-Z]{2})?/)?square/post/([A-Za-z0-9_-]+)",
    re.I,
)
ID_KEYS = ("postId", "post_id", "contentId", "content_id", "articleId", "article_id", "id")
TIME_KEYS = ("createTime", "createdAt", "posted_at", "published_at", "publishTime", "publishDate", "date", "releaseTime")
TEXT_KEYS = ("bodyTextOnly", "text", "content", "body", "description", "title", "subTitle")


def read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _public_page(url: str, timeout: float = 15.0) -> str:
    """Read a public first-party hashtag page without account/session credentials."""
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; NICPublicWTEDiscovery/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE + "/en/square",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_post_ids(page_html: str, limit: int = MAX_IDS_PER_HASHTAG) -> list[str]:
    """Extract public Square post IDs from links in the first-party hashtag page."""
    source = html.unescape(str(page_html or ""))
    source = source.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    found: list[str] = []
    seen: set[str] = set()
    for match in POST_ID_PATTERN.finditer(source):
        pid = normalize_id(match.group(1))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        found.append(pid)
        if len(found) >= max(0, int(limit)):
            break
    return found


def _same_post_id(row: dict, pid: str) -> bool:
    return any(row.get(key) is not None and normalize_id(row.get(key)) == normalize_id(pid) for key in ID_KEYS)


def _post_object(payload: Any, pid: str) -> dict:
    """Select one post detail record without mixing adjacent content cards."""
    data = _data_payload(payload)
    objects = list(_dicts(data))
    exact = [row for row in objects if _same_post_id(row, pid)]
    candidates = exact or objects

    def score(row: dict) -> int:
        has_body = any(row.get(key) not in (None, "", {}, []) for key in TEXT_KEYS)
        has_time = any(row.get(key) not in (None, "") for key in TIME_KEYS)
        has_author = any(row.get(key) not in (None, "") for key in (
            "authorName", "displayName", "nickName", "username", "squareUid", "authorId"
        ))
        return (5 if _same_post_id(row, pid) else 0) + (3 if has_body else 0) + (2 if has_time else 0) + (1 if has_author else 0)

    result = dict(max(candidates, key=score, default={}))
    result.setdefault("id", pid)
    body = _body_text(result)
    if not body:
        for item in objects:
            if any(item.get(key) not in (None, "", {}, []) for key in TEXT_KEYS):
                body = _body_text(item)
                if body:
                    break
    if body:
        result["bodyTextOnly"] = body
    if not any(result.get(key) not in (None, "") for key in TIME_KEYS):
        stamp = _first_value(data, TIME_KEYS)
        if stamp is not None:
            result["createTime"] = stamp
    if not any(result.get(key) not in (None, "") for key in ("authorName", "displayName", "nickName", "username")):
        for key in ("authorName", "displayName", "nickName", "username", "authorId", "squareUid"):
            value = _first_value(data, (key,))
            if value is not None:
                result[key] = value
    return result


def normalize_public_claim_post(payload: Any, pid: str, hashtag: str,
                                now: datetime | None = None) -> dict | None:
    """Normalize only dated public posts containing WTE context plus an amount."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    row = _post_object(payload, pid)
    text = _body_text(row)
    if len(text) < 20 or not AMOUNT_CONTEXT.search(text) or not CLAIM_ACTION.search(text):
        return None
    hashtag_context = str(hashtag or "").strip().lower().replace("-", "").replace("_", "")
    if not WTE_CONTEXT.search(text) and hashtag_context not in WTE_HASHTAG_SLUGS:
        return None
    stamp = posted_at(row)
    # The collector corpus uses the canonical `posted_at` field, while the raw
    # API normalizer intentionally prioritizes API timestamp aliases.
    if not stamp and row.get("posted_at") not in (None, ""):
        stamp = posted_at({"published_at": row.get("posted_at")})
    if not stamp:
        return None
    try:
        posted = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if posted.tzinfo is None or posted > now or posted < now - timedelta(days=14):
        return None

    name, uid = author(row)
    user = _user_object(payload) if isinstance(payload, (dict, list)) else {}
    if not uid:
        uid = _first_value(payload, ("squareUid", "authorId", "userId", "uid"))
    if not name:
        name = str(user.get("displayName") or user.get("nickName") or row.get("username") or "unknown").strip()
    profile_url = creator_profile_url(row)
    if not profile_url:
        # A genuine username field is an observed handle; a display name is not.
        handle = str(row.get("username") or row.get("userName") or "").strip()
        if handle and handle.lower() not in {"unknown", "null", "none"}:
            profile_url = f"{BASE}/en/square/profile/{urllib.parse.quote(handle, safe='')}"

    profile = {
        "creator": name or "unknown",
        "username": str(row.get("username") or row.get("userName") or "") or None,
        "square_uid": str(uid or "") or None,
        "creator_profile_url": profile_url,
    }
    row.update({"id": pid, "bodyTextOnly": text, "posted_at": stamp})
    normalized = _parse_profile_post(row, profile, now)
    if not normalized:
        return None
    normalized.update({
        "source_type": "public_wte_hashtag_claim_observation",
        "discovery_hashtag": hashtag,
        "earnings_status": "UNVERIFIED_PUBLIC_SELF_REPORT",
        "evidence_type": "PUBLIC_SELF_REPORTED_WRITE_TO_EARN_CLAIM",
        "metrics_scope": "public_post_metrics_only; reward claim is not independently verified",
    })
    return normalized


def _public_corpus_claim(row: dict, now: datetime) -> dict | None:
    """Identify recent public reward claims already present in the collector's feed corpus."""
    text = _body_text(row.get("text") or row.get("bodyTextOnly") or row.get("content") or "")
    if len(text) < 20 or not AMOUNT_CONTEXT.search(text) or not CLAIM_ACTION.search(text):
        return None
    if not WTE_CONTEXT.search(text):
        return None
    stamp = posted_at(row)
    # The normalized collector corpus stores its timestamp in `posted_at`,
    # while the raw API timestamp helper recognizes API aliases like published_at.
    if not stamp and row.get("posted_at") not in (None, ""):
        stamp = posted_at({"published_at": row.get("posted_at")})
    if not stamp:
        return None
    try:
        posted = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = now.astimezone(timezone.utc)
    if posted.tzinfo is None or posted > now or posted < now - timedelta(days=14):
        return None

    source_url = str(row.get("source_url") or row.get("source") or "").strip()
    parsed = urllib.parse.urlparse(source_url)
    host = (parsed.hostname or "").lower()
    official_host = host == "binance.com" or host.endswith(".binance.com")
    match = POST_ID_PATTERN.search(source_url)
    pid = normalize_id(row.get("post_id") or row.get("postId") or (match.group(1) if match else ""))
    if not pid:
        return None
    if not official_host or parsed.scheme != "https" or not match or normalize_id(match.group(1)) != pid:
        source_url = f"{BASE}/en/square/post/{urllib.parse.quote(pid, safe='')}"

    creator = str(row.get("creator") or row.get("authorName") or "unknown").strip()
    username = str(row.get("creator_username") or row.get("username") or row.get("userName") or "").strip()
    profile_url = str(row.get("creator_profile_url") or "").strip()
    if not profile_url and username and username.lower() not in {"unknown", "null", "none"}:
        profile_url = f"{BASE}/en/square/profile/{urllib.parse.quote(username, safe='')}"
    profile = {
        "creator": creator or "unknown",
        "username": username or None,
        "square_uid": str(row.get("creator_id") or row.get("squareUid") or row.get("authorId") or "") or None,
        "creator_profile_url": profile_url or None,
    }
    post_row = dict(row)
    post_row.update({
        "id": pid, "bodyTextOnly": text, "posted_at": posted.isoformat(),
        "published_at": posted.isoformat(), "source_url": source_url,
    })
    # Adapt already-normalized collector rows back to the public API metric keys
    # expected by the shared parser, preserving known zero versus unknown.
    if row.get("views") is not None:
        post_row.setdefault("viewCount", row.get("views"))
    if row.get("likes") is not None:
        post_row.setdefault("likeCount", row.get("likes"))
    if row.get("replies") is not None and row.get("reply_metric_status") != "SUSPICIOUS_COUNTER_EQUALS_OR_EXCEEDS_VIEWS":
        post_row.setdefault("commentCount", row.get("replies"))
    if row.get("shares") is not None:
        post_row.setdefault("shareCount", row.get("shares"))
    normalized = _parse_profile_post(post_row, profile, now)
    if not normalized:
        return None
    normalized.update({
        "source_type": "public_creator_feed_claim_observation",
        "discovery_hashtag": "existing_public_feed_corpus",
        "earnings_status": "UNVERIFIED_PUBLIC_SELF_REPORT",
        "evidence_type": "PUBLIC_SELF_REPORTED_WRITE_TO_EARN_CLAIM",
        "metrics_scope": "public_post_metrics_only; reward claim is not independently verified",
    })
    return normalized


def collect_public_claim_posts(now: datetime | None = None, page_fetch=_public_page,
                               detail_fetch=public_json_request, sleep_fn=time.sleep,
                               hashtag_slugs: tuple[str, ...] = HASHTAG_SLUGS,
                               public_examples: list[dict] | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    page_rows, page_errors = [], []
    seen_ids: set[str] = set()
    hashtag_for_id: dict[str, str] = {}
    for slug in hashtag_slugs:
        url = f"{BASE}/en/square/hashtag/{urllib.parse.quote(slug, safe='')}"
        try:
            page_source = page_fetch(url)
            ids = extract_post_ids(page_source, MAX_IDS_PER_HASHTAG)
            page_rows.append({"hashtag": slug, "status": "PAGE_READ", "post_ids_found": len(ids), "source_url": url})
            for pid in ids:
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    hashtag_for_id[pid] = slug
                if len(seen_ids) >= MAX_POST_DETAILS_PER_RUN:
                    break
        except Exception as exc:
            page_errors.append({"hashtag": slug, "status": "PUBLIC_PAGE_READ_FAILED_" + type(exc).__name__})
        if len(seen_ids) >= MAX_POST_DETAILS_PER_RUN:
            break

    normalized_posts, detail_errors = [], []
    ids_to_check = list(seen_ids)[:MAX_POST_DETAILS_PER_RUN]
    for index, pid in enumerate(ids_to_check):
        try:
            detail = detail_fetch(BASE + POST_DETAIL_API + urllib.parse.quote(pid, safe=""))
            post = normalize_public_claim_post(detail, pid, hashtag_for_id.get(pid, "unknown"), now)
            if post:
                normalized_posts.append(post)
        except Exception as exc:
            detail_errors.append({"post_id": pid, "status": "PUBLIC_POST_DETAIL_FAILED_" + type(exc).__name__})
        if index + 1 < len(ids_to_check):
            sleep_fn(REQUEST_DELAY_SECONDS)

    # Hashtag HTML often loads client-side without server-rendered post links.
    # The daily feed collector has already harvested hundreds of public posts, so
    # scan its dated corpus as a robust fallback instead of reporting zero leads
    # just because a hashtag page exposed no anchor IDs.
    corpus_checked = 0
    corpus_matched = 0
    seen_claim_ids = {normalize_id(row.get("post_id")) for row in normalized_posts if isinstance(row, dict)}
    for source_row in public_examples if isinstance(public_examples, list) else []:
        if not isinstance(source_row, dict):
            continue
        corpus_checked += 1
        post = _public_corpus_claim(source_row, now)
        if not post:
            continue
        corpus_matched += 1
        pid = normalize_id(post.get("post_id"))
        if pid and pid not in seen_claim_ids:
            normalized_posts.append(post)
            seen_claim_ids.add(pid)

    claim_report = analyze_public_reward_claims(normalized_posts, now)
    claimed_urls = set()
    for claim in claim_report.get("claims", []) if isinstance(claim_report.get("claims"), list) else []:
        if not isinstance(claim, dict):
            continue
        if claim.get("source_url"):
            claimed_urls.add(str(claim["source_url"]))
        for url in claim.get("sample_urls", []):
            claimed_urls.add(str(url))
    retained_claims = [row for row in normalized_posts if str(row.get("source_url") or "") in claimed_urls]
    return {
        "schema": "NIC-PUBLIC-WTE-CLAIM-DISCOVERY-1.0",
        "generated_at": now.isoformat(),
        "status": "PUBLIC_SELF_REPORTED_CLAIMS_FOUND" if retained_claims else (
            "PUBLIC_POSTS_CHECKED_NO_RECENT_CLAIMS" if normalized_posts else
            "HASHTAG_PAGES_READ_NO_RECENT_DATED_CLAIM_POSTS" if page_rows else
            "PUBLIC_HASHTAG_ENDPOINT_BLOCKED"
        ),
        "public_only": True,
        "authenticated_session_used": False,
        "cookies_or_api_keys_used": False,
        "hashtag_pages_checked": page_rows,
        "hashtag_page_errors": page_errors,
        "post_detail_requests": len(ids_to_check),
        "post_detail_errors": detail_errors,
        "public_corpus_rows_checked": corpus_checked,
        "public_corpus_claim_matches_before_deduplication": corpus_matched,
        "normalized_recent_claim_post_count": len(normalized_posts),
        "retained_recent_claim_post_count": len(retained_claims),
        "public_claim_creators_found": len({str(row.get("creator") or "").casefold() for row in retained_claims}),
        "claims": retained_claims,
        "claim_analysis": claim_report,
        "evidence_policy": {
            "public_claims_are_independently_verified": False,
            "creator_amounts_inferred_from_engagement": False,
            "public_claims_are_research_leads_only": True,
            "unknown_dates_excluded": True,
            "no_automated_engagement_or_publication": True,
        },
    }


def merge_examples(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for row in existing:
        if not isinstance(row, dict):
            continue
        pid = normalize_id(row.get("post_id") or row.get("postId") or row.get("source_url") or row.get("source"))
        if pid:
            by_id[pid] = dict(row)
    for row in incoming:
        pid = normalize_id(row.get("post_id") or row.get("postId"))
        if not pid:
            match = POST_ID_PATTERN.search(str(row.get("source_url") or ""))
            pid = normalize_id(match.group(1)) if match else ""
        if not pid:
            continue
        if pid not in by_id:
            by_id[pid] = dict(row)
        else:
            old = by_id[pid]
            merged = dict(old)
            for key, value in row.items():
                if value not in (None, "", {}, []):
                    if key not in merged or merged.get(key) in (None, "", {}, []):
                        merged[key] = value
            merged["research_sources"] = list(dict.fromkeys((merged.get("research_sources") or []) + ["public-wte-hashtag-claim-discovery"]))
            by_id[pid] = merged
    return list(by_id.values())[-MAX_EXAMPLES:]


def main() -> int:
    now = datetime.now(timezone.utc)
    examples = read_json(EXAMPLES, [])
    if not isinstance(examples, list):
        examples = []
    result = collect_public_claim_posts(now, public_examples=examples)
    write_json(OUT, result)
    write_json(EXAMPLES, merge_examples(examples, result.get("claims", [])))
    print(json.dumps({
        "status": result["status"],
        "hashtag_pages_checked": len(result["hashtag_pages_checked"]),
        "post_detail_requests": result["post_detail_requests"],
        "public_corpus_rows_checked": result["public_corpus_rows_checked"],
        "public_corpus_claim_matches": result["public_corpus_claim_matches_before_deduplication"],
        "recent_claim_posts": result["retained_recent_claim_post_count"],
        "claim_creators": result["public_claim_creators_found"],
        "authenticated_session_used": result["authenticated_session_used"],
        "output": str(OUT.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
