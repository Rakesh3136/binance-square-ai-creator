"""Bounded public Binance Square profile research for NIC.

Only public profile/post endpoints are queried. This module does not log in,
reuse browser cookies, replay fingerprint headers, publish, follow, like, or comment.
If a public endpoint blocks the request, the report records that limitation.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from src.nic_square_earnings_learning import analyze_public_reward_claims, extract_public_leaderboard_entries
    from src.nic_wte_leaderboard_evidence import normalize_observations
    from src.square_creator_benchmark_collector import archetype, metric, normalize_id, posted_at
except ModuleNotFoundError:
    from nic_square_earnings_learning import analyze_public_reward_claims, extract_public_leaderboard_entries
    from nic_wte_leaderboard_evidence import normalize_observations
    from square_creator_benchmark_collector import archetype, metric, normalize_id, posted_at

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_PATH = ROOT / "data/intelligence/public_square_examples.json"
BENCHMARK_PATH = ROOT / "data/intelligence/square_creator_benchmark.json"
OBSERVED_LEADERBOARD_PATH = ROOT / "data/intelligence/wte_leaderboard_observed.json"
OBSERVED_LEADERBOARD_INPUT_PATH = ROOT / "data/intelligence/wte_leaderboard_observations.json"
OUT_PATH = ROOT / "data/intelligence/nic_square_profile_research.json"

BASE = "https://www.binance.com"
USER_API = "/bapi/composite/v3/friendly/pgc/user/client"
POST_DETAIL_API = "/bapi/composite/v3/friendly/pgc/special/content/detail/"
USER_POSTS_API = "/bapi/composite/v2/friendly/pgc/content/queryUserProfilePageContentsWithFilter"
MAX_PROFILE_TARGETS = 12
MAX_PAGES_PER_PROFILE = 5
MAX_POSTS_PER_PROFILE = 40
MAX_EXAMPLES = 8000
REQUEST_DELAY_SECONDS = 0.35
MAX_BODY_TEXT = 900
UTC_MIN = datetime(2000, 1, 1, tzinfo=timezone.utc)


def read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def public_json_request(url: str, method: str = "GET", payload: dict | None = None,
                        timeout: float = 15.0) -> Any:
    """Call a public page endpoint without cookies, API keys, or fingerprint replay."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.binance.com/en/square",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _is_official_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "binance.com" or host.endswith(".binance.com"))


def profile_username(profile_url: object) -> str | None:
    if not _is_official_url(profile_url):
        return None
    parsed = urllib.parse.urlparse(str(profile_url).strip())
    match = re.search(r"/square/profile/([^/?#]+)", parsed.path, re.I)
    return urllib.parse.unquote(match.group(1)) if match else None


def post_id_from_url(post_url: object) -> str | None:
    if not _is_official_url(post_url):
        return None
    parsed = urllib.parse.urlparse(str(post_url).strip())
    match = re.search(r"/(?:en/)?square/post/([A-Za-z0-9_-]+)", parsed.path, re.I)
    return match.group(1) if match else None


def _data_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        if payload.get("success") is False or (payload.get("code") not in (None, "000000", 0, "0")):
            raise RuntimeError("public_endpoint_returned_error")
        return payload.get("data", payload)
    return payload


def _dicts(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _dicts(value)
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                yield from _dicts(value)


def _first_value(payload: Any, keys: tuple[str, ...]) -> str | None:
    for item in _dicts(payload):
        for key in keys:
            value = item.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return None


def _user_object(payload: Any) -> dict:
    for item in _dicts(payload):
        if any(item.get(key) not in (None, "") for key in ("squareUid", "username", "displayName", "userShareLink")):
            return item
    return {}


def _body_text(value: Any, depth: int = 0) -> str:
    if depth > 5:
        return ""
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return ""
        if raw.startswith("{") or raw.startswith("["):
            try:
                nested = json.loads(raw)
                extracted = _body_text(nested, depth + 1)
                if extracted:
                    return extracted
            except json.JSONDecodeError:
                pass
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"https?://\S+", "", raw)
        return re.sub(r"\s+", " ", raw).strip()[:MAX_BODY_TEXT]
    if isinstance(value, dict):
        parts = []
        preferred = ("bodyTextOnly", "text", "content", "title", "subTitle", "description", "textContent")
        for key in preferred:
            if key in value:
                part = _body_text(value[key], depth + 1)
                if part and part not in parts:
                    parts.append(part)
        if not parts:
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    part = _body_text(nested, depth + 1)
                    if part and part not in parts:
                        parts.append(part)
        return " ".join(parts)[:MAX_BODY_TEXT]
    if isinstance(value, list):
        parts = []
        for item in value[:60]:
            part = _body_text(item, depth + 1)
            if part and part not in parts:
                parts.append(part)
        return " ".join(parts)[:MAX_BODY_TEXT]
    return ""


def _post_stamp(row: dict) -> str | None:
    # The existing collector normalizes seconds, milliseconds, and ISO timestamps.
    return posted_at(row)


def _post_url(row: dict, post_id: str) -> str:
    for key in ("webLink", "shareLink", "shareUrl", "url", "link"):
        value = row.get(key)
        if isinstance(value, str) and "/post/" in value and _is_official_url(value):
            return value
    return f"https://www.binance.com/en/square/post/{urllib.parse.quote(post_id, safe='')}"


def build_candidates(examples: list[dict], benchmark: dict, observed: dict,
                     now: datetime | None = None, limit: int = MAX_PROFILE_TARGETS) -> list[dict]:
    """Prioritize observed leaderboard rows, public leaderboard leads, then top public creators."""
    now = now or datetime.now(timezone.utc)
    candidates: list[dict] = []
    seen: set[str] = set()

    def add(row: dict, source: str, score: tuple = (0, 0)) -> None:
        name = str(row.get("creator") or row.get("claimed_creator") or "").strip().lstrip("@")
        url = row.get("creator_profile_url") or row.get("profile_url")
        username = profile_username(url) if url else None
        if not name and username:
            name = username
        samples = row.get("sample_urls") or row.get("recent_post_urls") or []
        if not isinstance(samples, list):
            samples = []
        samples = [str(v) for v in samples if post_id_from_url(v)][:5]
        if not name and not username:
            return
        key = (username or name).casefold()
        if key in seen:
            # Merge new provenance/sample URLs into the existing candidate.
            for existing in candidates:
                if (existing.get("username") or existing.get("creator") or "").casefold() == key:
                    existing["sample_urls"] = list(dict.fromkeys(existing.get("sample_urls", []) + samples))[:5]
                    if not existing.get("creator_profile_url") and url:
                        existing["creator_profile_url"] = url
                    existing.setdefault("discovery_sources", []).append(source)
                    if source == "observed_write_to_earn_leaderboard":
                        existing["earnings_status"] = "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT"
                    break
            return
        seen.add(key)
        candidates.append({
            "creator": name or username,
            "username": username,
            "creator_profile_url": url if profile_username(url) else None,
            "sample_urls": samples,
            "discovery_source": source,
            "discovery_sources": [source],
            "claimed_amount": row.get("displayed_amount", row.get("claimed_amount")),
            "claimed_currency": row.get("currency", row.get("claimed_currency")),
            "rank": row.get("rank"),
            "evidence_ref": row.get("evidence_ref"),
            "source_url": row.get("source_url"),
            "earnings_status": ("OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT"
                                if source == "observed_write_to_earn_leaderboard"
                                else "PUBLIC_RESEARCH_LEAD_NOT_VERIFIED"),
            "priority": score,
        })

    entries = observed.get("entries", []) if isinstance(observed, dict) else []
    for row in entries if isinstance(entries, list) else []:
        if isinstance(row, dict):
            add(row, "observed_write_to_earn_leaderboard",
                (3, float(row.get("displayed_amount") or 0)))

    leaderboard_posts = extract_public_leaderboard_entries(examples, now)
    leaderboard_posts.sort(key=lambda x: float(x.get("claimed_amount") or 0), reverse=True)
    for row in leaderboard_posts:
        add(row, "public_leaderboard_post",
            (2, float(row.get("claimed_amount") or 0)))

    claim_report = analyze_public_reward_claims(examples, now)
    for row in claim_report.get("claims", []):
        if isinstance(row, dict):
            add(row, "public_self_reported_creator",
                (1, float(row.get("claim_posts_14d") or 0)))

    creators = benchmark.get("creator_benchmarks", []) if isinstance(benchmark, dict) else []
    for row in creators if isinstance(creators, list) else []:
        if isinstance(row, dict):
            add(row, "public_performance_benchmark",
                (0, float(row.get("mean_public_engagement_rate") or 0)))

    source_rank = {
        "observed_write_to_earn_leaderboard": 0,
        "public_leaderboard_post": 1,
        "public_self_reported_creator": 2,
        "public_performance_benchmark": 3,
    }
    candidates.sort(key=lambda row: (source_rank.get(row["discovery_source"], 9),
                                    -float(row["priority"][1]), row["creator"].casefold()))
    return candidates[:max(0, limit)]


def _resolve_user(candidate: dict, request_json=public_json_request) -> tuple[dict, str]:
    # Use an observed profile handle when present. Otherwise resolve a sample
    # public post to its author; never derive a profile URL from a display name.
    username = candidate.get("username") or profile_username(candidate.get("creator_profile_url"))
    user = {}
    uid = None
    last_error = "public_identifier_not_resolved"

    if not username:
        for url in candidate.get("sample_urls", []):
            post_id = post_id_from_url(url)
            if not post_id:
                continue
            try:
                detail = _data_payload(request_json(BASE + POST_DETAIL_API + urllib.parse.quote(post_id, safe="")))
                uid = _first_value(detail, ("squareUid", "squareAuthorId", "authorUid", "authorId", "userId", "uid"))
                user = _user_object(detail)
                if uid:
                    break
            except Exception as exc:
                last_error = "post_detail_" + type(exc).__name__
                break

    if not uid:
        identity = {"username": username} if username else {"username": str(candidate.get("creator") or "").strip().lstrip("@")}
        name = identity.get("username")
        if name and len(name) <= 100:
            try:
                response = request_json(BASE + USER_API, "POST", {
                    **identity, "getFollowCount": True,
                    "queryFollowersInfo": False, "queryRelationTokens": False,
                })
                data = _data_payload(response)
                user = _user_object(data)
                uid = _first_value(data, ("squareUid", "userId", "uid"))
                username = _first_value(data, ("username",)) or username
                if not uid:
                    last_error = "user_lookup_returned_no_square_uid"
            except Exception as exc:
                last_error = "user_lookup_" + type(exc).__name__

    if uid and not user.get("squareUid"):
        try:
            response = request_json(BASE + USER_API, "POST", {
                "squareUid": uid, "getFollowCount": True,
                "queryFollowersInfo": False, "queryRelationTokens": False,
            })
            data = _data_payload(response)
            found = _user_object(data)
            if found:
                user = {**user, **found}
            username = _first_value(data, ("username",)) or username
        except Exception as exc:
            # A public post detail may still supply enough identity to fetch posts.
            last_error = "profile_lookup_" + type(exc).__name__

    uid = str(user.get("squareUid") or uid or "").strip()
    username = str(user.get("username") or username or "").strip() or None
    display_name = str(user.get("displayName") or user.get("nickName") or candidate.get("creator") or username or "").strip()
    profile_url = user.get("userShareLink") or user.get("profileUrl") or user.get("webLink")
    if not profile_username(profile_url):
        profile_url = f"https://www.binance.com/en/square/profile/{urllib.parse.quote(username, safe='')}" if username else candidate.get("creator_profile_url")
    if not uid:
        raise RuntimeError(last_error)
    return ({
        "creator": candidate.get("creator") or display_name,
        "username": username,
        "display_name": display_name,
        "square_uid": uid,
        "creator_profile_url": profile_url if profile_username(profile_url) else None,
        "followers": user.get("totalFollowerCount"),
        "biography": str(user.get("biography") or "")[:500],
        "profile_source": "PUBLIC_BINANCE_SQUARE_PROFILE_ENDPOINT",
    }, uid)


def _parse_profile_post(row: dict, profile: dict, now: datetime) -> dict | None:
    pid = normalize_id(row.get("id") or row.get("postId") or row.get("contentId") or row.get("articleId"))
    if not pid:
        return None
    text = _body_text(row.get("bodyTextOnly") or row.get("content") or row.get("text") or
                      row.get("body") or row.get("description") or row.get("title") or row.get("subTitle"))
    stamp = _post_stamp(row)
    if not text or not stamp:
        return None
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt > now or dt < UTC_MIN or dt < now - timedelta(days=14):
        return None
    views = metric(row, "viewCount", "views", "view_num", "viewNum")
    likes = metric(row, "likeCount", "likes", "like_num", "likeNum")
    replies = metric(row, "commentCount", "comments", "replyCount", "replyNum", "commentNum")
    shares = metric(row, "shareCount", "shares", "shareNum")
    return {
        "source_type": "creator_profile_public_observation",
        "post_id": pid,
        "creator": profile.get("creator") or profile.get("username") or "unknown",
        "creator_id": profile.get("square_uid"),
        "creator_username": profile.get("username"),
        "creator_profile_url": profile.get("creator_profile_url"),
        "display_name": profile.get("display_name"),
        "source_url": _post_url(row, pid),
        "text": text[:MAX_BODY_TEXT],
        "posted_at": stamp,
        "archetype": archetype(text),
        "format": str(row.get("contentType") or row.get("cardType") or "unknown")[:80],
        "views": views, "likes": likes, "replies": replies, "shares": shares,
        "followers_gained": None,
        "observed_at": now.isoformat(),
        "metrics_scope": "public_profile_post_metrics_only; follower_delta_and_write_to_earn_reward_not_publicly_available",
        "earnings_status": "NOT_PUBLICLY_VERIFIED",
        "evidence_type": "PUBLIC_PROFILE_POST_OBSERVATION",
    }


def _extract_post_rows(page_payload: Any) -> tuple[list[dict], Any, bool]:
    data = _data_payload(page_payload)
    if not isinstance(data, dict):
        return [], None, False
    rows = data.get("contents") if isinstance(data.get("contents"), list) else data.get("vos")
    if not isinstance(rows, list):
        rows = []
    cursor = data.get("timeOffset")
    has_more = bool(data.get("isExistSecondPage"))
    return [r for r in rows if isinstance(r, dict)], cursor, has_more


def _fetch_profile_posts(uid: str, profile: dict, now: datetime, request_json=public_json_request,
                         sleep_fn=time.sleep) -> tuple[list[dict], str, int]:
    collected: dict[str, dict] = {}
    cursor: Any = int(now.timestamp() * 1000)
    status = "PROFILE_POSTS_COLLECTED"
    pages = 0
    try:
        for _ in range(MAX_PAGES_PER_PROFILE):
            query = urllib.parse.urlencode({
                "targetSquareUid": uid, "timeOffset": cursor, "filterType": "ALL",
            })
            response = request_json(BASE + USER_POSTS_API + "?" + query)
            rows, next_cursor, has_more = _extract_post_rows(response)
            pages += 1
            added_before = len(collected)
            for row in rows:
                post = _parse_profile_post(row, profile, now)
                if post:
                    collected[post["post_id"]] = post
            if len(collected) >= MAX_POSTS_PER_PROFILE:
                break
            if not has_more or not next_cursor or str(next_cursor) == str(cursor) or not rows:
                break
            # The API's cursor is honored exactly as returned; it is not inferred.
            cursor = next_cursor
            if len(collected) == added_before and rows:
                row_dates = [_post_stamp(r) for r in rows]
                dated = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in row_dates if v]
                if dated and max(dated) < now - timedelta(days=14):
                    break
            sleep_fn(REQUEST_DELAY_SECONDS)
    except Exception as exc:
        if collected:
            status = "PARTIAL_PROFILE_POSTS_" + type(exc).__name__
        else:
            status = "PROFILE_POST_ENDPOINT_BLOCKED_" + type(exc).__name__
    posts = sorted(collected.values(), key=lambda p: p["posted_at"], reverse=True)[:MAX_POSTS_PER_PROFILE]
    return posts, status, pages


def _merge_example_rows(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for row in existing:
        if not isinstance(row, dict):
            continue
        key = normalize_id(row.get("post_id") or row.get("source_url") or row.get("source"))
        if key:
            by_id[key] = dict(row)
    for row in incoming:
        key = normalize_id(row.get("post_id"))
        if not key:
            continue
        if key not in by_id:
            by_id[key] = row
            continue
        old = by_id[key]
        merged = dict(old)
        for field, value in row.items():
            if value not in (None, "", {}, []):
                if field not in merged or merged.get(field) in (None, "", {}, []):
                    merged[field] = value
        for field in ("views", "likes", "replies", "shares"):
            if not merged.get(field) and row.get(field):
                merged[field] = row[field]
        merged["creator_profile_url"] = merged.get("creator_profile_url") or row.get("creator_profile_url")
        merged["research_sources"] = list(dict.fromkeys((merged.get("research_sources") or []) + ["profile-directed-public-fetch"]))
        by_id[key] = merged
    return list(by_id.values())[-MAX_EXAMPLES:]


def research_profiles(candidates: list[dict], now: datetime | None = None,
                     request_json=public_json_request, sleep_fn=time.sleep) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    all_posts: list[dict] = []
    profiles, failures = [], []
    for index, candidate in enumerate(candidates[:MAX_PROFILE_TARGETS]):
        if not isinstance(candidate, dict):
            continue
        try:
            profile, uid = _resolve_user(candidate, request_json)
            posts, posts_status, pages = _fetch_profile_posts(uid, profile, now, request_json, sleep_fn)
            seven = [p for p in posts if datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")) >= now - timedelta(days=7)]
            fourteen = [p for p in posts if datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")) >= now - timedelta(days=14)]
            profiles.append({
                **profile,
                "discovery_source": candidate.get("discovery_source"),
                "earnings_status": candidate.get("earnings_status") or "PUBLIC_RESEARCH_LEAD_NOT_VERIFIED",
                "claimed_amount": candidate.get("claimed_amount"),
                "claimed_currency": candidate.get("claimed_currency"),
                "rank": candidate.get("rank"),
                "evidence_ref": candidate.get("evidence_ref"),
                "source_url": candidate.get("source_url"),
                "posts_7d": len(seven), "posts_14d": len(fourteen),
                "posts_age_8_to_14_days": sum(1 for p in fourteen if datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")) < now - timedelta(days=7)),
                "pages_checked": pages,
                "posts_status": posts_status,
                "recent_post_samples": [{
                    "post_url": p["source_url"], "posted_at": p["posted_at"], "archetype": p["archetype"],
                    "format": p["format"], "views": p["views"], "likes": p["likes"],
                    "replies": p["replies"], "shares": p["shares"],
                } for p in posts[:10]],
            })
            all_posts.extend(posts)
        except Exception as exc:
            failures.append({
                "creator": str(candidate.get("creator") or candidate.get("username") or "unknown")[:120],
                "discovery_source": candidate.get("discovery_source"),
                "status": "PROFILE_RESOLUTION_BLOCKED_" + type(exc).__name__,
            })
        if index + 1 < min(len(candidates), MAX_PROFILE_TARGETS):
            sleep_fn(REQUEST_DELAY_SECONDS)

    seven_count = sum(1 for p in all_posts if datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")) >= now - timedelta(days=7))
    older_count = sum(1 for p in all_posts if now - timedelta(days=14) <= datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00")) < now - timedelta(days=7))
    status = "PROFILE_RESEARCH_COMPLETE" if profiles and all_posts else (
        "PROFILES_RESOLVED_NO_DATED_POSTS" if profiles else
        "PUBLIC_PROFILE_ENDPOINT_BLOCKED" if failures else "NO_PROFILE_CANDIDATES"
    )
    return {
        "schema": "NIC-SQUARE-PUBLIC-PROFILE-RESEARCH-1.0",
        "generated_at": now.isoformat(),
        "status": status,
        "public_only": True,
        "authenticated_session_used": False,
        "cookies_or_api_keys_used": False,
        "profile_target_limit": MAX_PROFILE_TARGETS,
        "post_page_limit_per_profile": MAX_PAGES_PER_PROFILE,
        "candidate_count": min(len(candidates), MAX_PROFILE_TARGETS),
        "profiles_resolved": len(profiles),
        "profile_resolution_failures": len(failures),
        "posts_collected_7d": seven_count,
        "posts_collected_8_to_14d": older_count,
        "posts_collected_14d": len(all_posts),
        "seven_day_coverage_observed": seven_count > 0,
        "fourteen_day_coverage_observed": older_count > 0,
        "public_metrics_are_not_earnings": True,
        "profiles": profiles,
        "posts": all_posts,
        "failures": failures,
        "policy": {
            "only_public_profile_and_post_data": True,
            "no_likes_follows_comments_or_publishing": True,
            "unknown_dates_excluded": True,
            "creator_reward_amounts_not_inferred": True,
            "if_endpoints_block_requests": "Record endpoint blocked status; do not use cookies or fingerprint-header replay to bypass the block.",
        },
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    examples = read_json(EXAMPLES_PATH, [])
    benchmark = read_json(BENCHMARK_PATH, {})
    observation_input = read_json(OBSERVED_LEADERBOARD_INPUT_PATH, {"entries": []})
    observed = normalize_observations(observation_input, now)
    write_json(OBSERVED_LEADERBOARD_PATH, observed)
    if not isinstance(examples, list):
        examples = []
    candidates = build_candidates(examples, benchmark, observed, now)
    result = research_profiles(candidates, now)
    write_json(OUT_PATH, result)
    # Keep profile-retrieved observations in the shared public-example corpus so
    # creator intelligence and the learning planner evaluate the same samples.
    merged = _merge_example_rows(examples, result.get("posts", []))
    write_json(EXAMPLES_PATH, merged)
    print(json.dumps({
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "profiles_resolved": result["profiles_resolved"],
        "posts_collected_7d": result["posts_collected_7d"],
        "posts_collected_8_to_14d": result["posts_collected_8_to_14d"],
        "profile_resolution_failures": result["profile_resolution_failures"],
        "output": str(OUT_PATH.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
