"""Monetization-focused NIC learning from rolling public creator research.

The target is an optimization goal, not a promise. Public creator metrics are not
earnings proof; only exact-post, source-backed reward events count as verified pay.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from src.nic_reward_evidence import is_verified_reward_event, canonical_post_id, reward_event_rejection_reasons
    from src.nic_wte_leaderboard_evidence import normalize_observations
except ModuleNotFoundError:
    from nic_reward_evidence import is_verified_reward_event, canonical_post_id, reward_event_rejection_reasons
    from nic_wte_leaderboard_evidence import normalize_observations

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
INTEL = ROOT / "data/intelligence"
LIVE = ROOT / "data/live"
BENCHMARK = INTEL / "square_creator_benchmark.json"
PATTERNS = INTEL / "creator_patterns.json"
EXAMPLES = INTEL / "public_square_examples.json"
REWARD_EVENTS = ANALYTICS / "wte_reward_events.jsonl"
OWNER_REPORTED_REWARDS = ANALYTICS / "wte_owner_reported_reward_events.jsonl"
ATTRIBUTION = ANALYTICS / "publication_attribution.jsonl"
PERFORMANCE = ANALYTICS / "square_performance.jsonl"
OUT = LIVE / "nic_square_earnings_learning.json"
REPORT = INTEL / "nic_square_earnings_learning_report.json"
MEMORY = ANALYTICS / "nic_square_earnings_learning_memory.json"
OFFICIAL_PROGRAM_URL = "https://www.binance.com/en/square/profile/binance_square_official"
DEFAULT_WEEKLY_TARGET_USDC = 200.0


def load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except (OSError, json.JSONDecodeError):
        return default


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
        except json.JSONDecodeError:
            continue
    return result


def number(row: dict, *keys: str) -> float:
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    for source in (row, metrics):
        for key in keys:
            try:
                value = float(source.get(key))
                if value == value and abs(value) != float("inf"):
                    return value
            except (TypeError, ValueError):
                continue
    return 0.0


def aware_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def weekly_target() -> float:
    try:
        value = float(os.environ.get("NIC_WEEKLY_REVENUE_TARGET_USDC", DEFAULT_WEEKLY_TARGET_USDC))
        return value if value > 0 and value < 1_000_000 else DEFAULT_WEEKLY_TARGET_USDC
    except (TypeError, ValueError):
        return DEFAULT_WEEKLY_TARGET_USDC


def summarize_own_content(now: datetime, attribution_rows: list[dict], performance_rows: list[dict]) -> dict:
    """Join exact post IDs and use latest visible Square metrics per post."""
    attrib = {}
    for row in attribution_rows:
        pid = canonical_post_id(row)
        if pid:
            attrib[pid] = row

    latest = {}
    for row in performance_rows:
        pid = canonical_post_id(row)
        if not pid or pid not in attrib:
            continue
        stamp = aware_time(row.get("collected_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if pid not in latest or stamp >= latest[pid][0]:
            latest[pid] = (stamp, row)

    per_window = {}
    for days in (7, 14):
        cutoff = now - timedelta(days=days)
        groups = defaultdict(list)
        eligible = []
        for pid, (stamp, perf) in latest.items():
            publication = attrib[pid]
            published = aware_time(publication.get("published_at") or publication.get("timestamp"))
            if not published or published < cutoff or published > now:
                continue
            category = str(publication.get("category") or "unknown")
            metrics = perf.get("metrics") if isinstance(perf.get("metrics"), dict) else {}
            follow_keys = ("follows", "new_follows", "followers_gained")
            follows_observed = any(key in perf or key in metrics for key in follow_keys)
            sample = {
                "views": number(perf, "views", "view_count", "impressions"),
                "likes": number(perf, "likes", "like_count"),
                "replies": number(perf, "comments", "replies", "reply_count"),
                "shares": number(perf, "shares", "share_count"),
                "follows": number(perf, *follow_keys) if follows_observed else None,
                "follows_observed": follows_observed,
            }
            eligible.append(sample)
            groups[category].append(sample)
        def aggregate(samples: list[dict]) -> dict:
            n = len(samples)
            views = sum(x["views"] for x in samples)
            likes = sum(x["likes"] for x in samples)
            replies = sum(x["replies"] for x in samples)
            shares = sum(x["shares"] for x in samples)
            observed_follow_rows = [x for x in samples if x.get("follows_observed")]
            follows = sum(x["follows"] for x in observed_follow_rows)
            return {
                "posts": n,
                "avg_views": round(views / n, 2) if n else None,
                "total_views": round(views, 2),
                "reply_rate_per_view": round(replies / max(1, views), 6),
                "share_rate_per_view": round(shares / max(1, views), 6),
                "weighted_engagement_per_1000_views": round((likes + 2 * replies + 3 * shares) * 1000 / max(1, views), 4),
                "total_follows": follows if observed_follow_rows else None,
                "follow_metric_coverage_posts": len(observed_follow_rows),
                "follow_rate_per_view": round(follows / max(1, views), 6) if observed_follow_rows else None,
                "weighted_engagement_formula": "internal proxy: likes + 2*comments + 3*shares; follows tracked separately because Binance's proprietary weights are not public",
                "evidence": "OWN_ACCOUNT_PUBLIC_METRICS_NOT_REVENUE",
            }
        per_window[str(days) + "_day"] = {
            **aggregate(eligible),
            "by_content_lane": [
                {"content_lane": lane, **aggregate(rows)}
                for lane, rows in sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
            ][:10],
        }
    return per_window


def collect_verified_rewards(events: list[dict], now: datetime) -> dict:
    accepted = [event for event in events if is_verified_reward_event(event)]
    seen = set()
    unique = []
    duplicates = 0
    for event in accepted:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id or event_id in seen:
            duplicates += 1
            continue
        seen.add(event_id)
        unique.append(event)

    cutoff = now - timedelta(days=7)
    recent = []
    for event in unique:
        verified_at = aware_time(event.get("verified_at"))
        if verified_at and cutoff <= verified_at <= now:
            recent.append(event)
    amount = sum(number(event, "reward_amount_usdc") for event in recent)
    rejected = [event for event in events if not is_verified_reward_event(event)]
    reasons = Counter(reason for event in rejected for reason in reward_event_rejection_reasons(event))
    return {
        "accepted_unique_reward_events_total": len(unique),
        "accepted_unique_reward_events_7d": len(recent),
        "verified_usdc_7d": round(amount, 8) if recent else None,
        "verified_usdc_7d_status": "MEASURED_FROM_VERIFIED_POST_LINKED_EVENTS" if recent else "NO_VERIFIED_POST_LINKED_REWARD_DATA",
        "rejected_events": len(rejected),
        "duplicate_event_ids_ignored": duplicates,
        "rejection_reason_counts": dict(reasons),
        "exact_post_attribution_required": True,
        "public_metrics_used_as_revenue": False,
    }


def summarize_owner_reported_reward_feedback(events: list[dict], now: datetime) -> dict:
    """Summarize exact-post reward reports supplied by the account owner without upgrading their verification status."""
    cutoff_7d = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)
    seen_event_ids = set()
    accepted = []
    rejected = 0
    duplicates = 0
    for event in events:
        if not isinstance(event, dict):
            rejected += 1
            continue
        event_id = str(event.get("event_id") or "").strip()
        post_id = canonical_post_id(event)
        reported_at = aware_time(event.get("reported_at"))
        currency = str(event.get("currency") or "").strip().upper()
        amount_raw = event.get("reward_amount_usdc")
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if (not event_id or event_id in seen_event_ids or not post_id or not reported_at
                or reported_at > now or amount < 0 or currency != "USDC"):
            if event_id and event_id in seen_event_ids:
                duplicates += 1
            else:
                rejected += 1
            continue
        seen_event_ids.add(event_id)
        meta = event.get("content_metadata") if isinstance(event.get("content_metadata"), dict) else {}
        url = str(meta.get("public_post_url") or event.get("public_post_url") or "").strip()
        parsed_url = urllib.parse.urlparse(url) if url else None
        host = (parsed_url.hostname or "").lower() if parsed_url else ""
        official_host = host == "binance.com" or host.endswith(".binance.com")
        url_match = re.search(r"/(?:en/)?square/post/([A-Za-z0-9_-]+)", parsed_url.path, re.I) if parsed_url else None
        if not parsed_url or parsed_url.scheme != "https" or not official_host or not url_match or url_match.group(1) != post_id:
            url = None
        accepted.append({
            "event_id": event_id,
            "post_id": post_id,
            "public_post_url": url,
            "reported_at": reported_at.isoformat(),
            "reported_reward_usdc": round(amount, 8),
            "currency": currency,
            "report_source": str(event.get("report_source") or "ACCOUNT_OWNER_REPORTED")[:80],
            "owner_reported_views": number(meta, "owner_reported_views") if meta.get("owner_reported_views") is not None else None,
            "content_lane": str(meta.get("content_lane") or "unknown")[:100],
            "content_format": str(meta.get("content_format") or "unknown")[:100],
            "hook_type": str(meta.get("hook_type") or "unknown")[:120],
            "summary": str(meta.get("summary") or "")[:1000],
            "verification_status": "OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "evidence_type": "ACCOUNT_OWNER_REPORTED_EXACT_POST_REWARD",
        })
    accepted.sort(key=lambda row: row["reported_at"], reverse=True)
    recent_7d = [row for row in accepted if cutoff_7d <= aware_time(row["reported_at"]) <= now]
    recent_14d = [row for row in accepted if cutoff_14d <= aware_time(row["reported_at"]) <= now]

    def aggregate(rows: list[dict]) -> dict:
        by_lane = defaultdict(list)
        for row in rows:
            by_lane[row["content_lane"]].append(row)
        return {
            "reported_event_count": len(rows),
            "post_count": len({row["post_id"] for row in rows}),
            "reported_usdc": round(sum(row["reported_reward_usdc"] for row in rows), 8) if rows else None,
            "rows_with_reported_views": sum(1 for row in rows if row["owner_reported_views"] is not None),
            "total_owner_reported_views": sum(row["owner_reported_views"] or 0 for row in rows) if any(row["owner_reported_views"] is not None for row in rows) else None,
            "by_content_lane": [{
                "content_lane": lane,
                "reported_event_count": len(values),
                "post_count": len({row["post_id"] for row in values}),
                "reported_usdc": round(sum(row["reported_reward_usdc"] for row in values), 8),
                "evidence_type": "OWNER_REPORTED_FEEDBACK_NOT_INDEPENDENTLY_VERIFIED",
            } for lane, values in sorted(by_lane.items(), key=lambda item: sum(row["reported_reward_usdc"] for row in item[1]), reverse=True)],
        }
    return {
        "status": "OWNER_REPORTED_FEEDBACK_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED" if accepted else "NO_OWNER_REPORTED_FEEDBACK",
        "evidence_type": "ACCOUNT_OWNER_REPORTED_EXACT_POST_REWARD",
        "independently_verified": False,
        "included_in_verified_reward_totals": False,
        "public_metrics_used_as_reward_proof": False,
        "accepted_report_count": len(accepted),
        "rejected_report_count": rejected,
        "duplicate_event_ids_ignored": duplicates,
        "7_day": aggregate(recent_7d),
        "14_day": aggregate(recent_14d),
        "entries": accepted[:100],
        "policy": "Use as owner-reported directional learning feedback only; do not label as independently verified or mix into verified payout totals.",
    }


def extract_public_leaderboard_entries(examples: list[dict], now: datetime) -> list[dict]:
    """Extract named amounts from public leaderboard posts as research leads, never payout proof."""
    context = re.compile(r"write[- ]to[- ]earn|leaderboard|top creators|weekly rewards|creator rewards|earnings season|weekly earnings|reward winners", re.I)
    entry = re.compile(r"@([A-Za-z0-9_.-]{2,50})[^@]{0,45}?(?:💰\s*)?\$?\s*(\d{2,3}(?:,\d{3})*(?:\.\d+)?)\s*(USDC|USDT|USD)?", re.I)
    cutoff = now - timedelta(days=14)
    results, seen = [], set()
    for row in examples:
        if not isinstance(row, dict): continue
        body = str(row.get("text") or row.get("post") or row.get("title") or "")
        if not body or not context.search(body): continue
        posted = aware_time(row.get("posted_at") or row.get("published_at"))
        if not posted or posted < cutoff or posted > now: continue
        for match in entry.finditer(body):
            name, raw_amount, currency = match.groups()
            try: amount = float(raw_amount.replace(",", ""))
            except ValueError: continue
            if amount <= 0: continue
            chosen_currency = (currency or ("USD" if "$" in match.group(0) else "UNSPECIFIED")).upper()
            key = (str(row.get("post_id") or ""), name.casefold(), amount, chosen_currency)
            if key in seen: continue
            seen.add(key)
            results.append({"claimed_creator": name, "claimed_amount": amount, "claimed_currency": chosen_currency, "source_publisher": str(row.get("creator") or row.get("creator_id") or "unknown")[:120], "source_post_id": str(row.get("post_id") or ""), "source_url": str(row.get("source_url") or row.get("source") or "")[:400], "posted_at": posted.isoformat(), "window_days": 14, "earnings_status": "PUBLIC_LEADERBOARD_CLAIM_NOT_INDEPENDENTLY_VERIFIED", "evidence_type": "PUBLIC_LEADERBOARD_RESEARCH_LEAD"})
    return sorted(results, key=lambda x: (x["posted_at"], x["claimed_amount"]), reverse=True)[:100]
def analyze_public_reward_claims(examples: list[dict], now: datetime) -> dict:
    """Find public self-reported earnings posts for research, never as payout proof."""
    amount_re = re.compile(r"\b(?:USD\s*)?\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:USDC|USDT|USD)\b", re.IGNORECASE)
    self_report = re.compile(r"\b(i earned|i made|i received|my earnings|my reward|my payout|we earned|we made|paid me|earned from write[- ]to[- ]earn)\b", re.IGNORECASE)
    cutoff = now - timedelta(days=14)
    claims = defaultdict(list)
    undated_count = 0
    for row in examples:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or row.get("post") or row.get("title") or "")
        if not text or not amount_re.search(text) or not self_report.search(text):
            continue
        posted = aware_time(row.get("posted_at") or row.get("published_at"))
        if not posted:
            undated_count += 1
            continue
        if posted < cutoff or posted > now:
            continue
        creator = str(row.get("creator") or row.get("creator_id") or "unknown")[:120]
        post_id = str(row.get("post_id") or "").strip()
        key = str(row.get("creator_id") or creator)
        claims[key].append({
            "creator": creator,
            "post_id": post_id,
            "source_url": str(row.get("source_url") or row.get("source") or "")[:400],
            "posted_at": posted.isoformat(),
        })
    candidates = []
    for key, rows in claims.items():
        rows.sort(key=lambda row: row["posted_at"], reverse=True)
        candidates.append({
            "creator": rows[0]["creator"],
            "creator_id": key,
            "claim_posts_14d": len(rows),
            "latest_claim_at": rows[0]["posted_at"],
            "sample_urls": [row["source_url"] for row in rows[:5] if row["source_url"]],
            "post_ids": [row["post_id"] for row in rows[:5] if row["post_id"]],
            "earnings_status": "UNVERIFIED_PUBLIC_SELF_REPORT",
            "evidence_type": "PUBLIC_CLAIM_NOT_PAYMENT_PROOF",
        })
    candidates.sort(key=lambda row: (row["claim_posts_14d"], row["latest_claim_at"]), reverse=True)
    return {
        "window_days": 14,
        "public_claim_post_count": sum(len(rows) for rows in claims.values()),
        "distinct_claiming_creators": len(candidates),
        "undated_claims_excluded": undated_count,
        "claims": candidates[:30],
        "public_leaderboard_entries": extract_public_leaderboard_entries(examples, now),
        "warning": "Self-reported public claims may be useful leads but are not verified payout records and never enter NIC's revenue labels.",
    }


def summarize_leaderboard_creator_posts(examples: list[dict], entries: list[dict], now: datetime) -> dict:
    """Summarize public posts by named leaderboard creators over 7/14 days; never infer payout causality."""
    targets = {str(row.get("claimed_creator") or "").strip().lstrip("@").casefold() for row in entries if row.get("claimed_creator")}
    selected = []
    for row in examples:
        if not isinstance(row, dict): continue
        name = str(row.get("creator") or "").strip().lstrip("@").casefold()
        if name not in targets: continue
        stamp = aware_time(row.get("posted_at") or row.get("published_at"))
        if not stamp or stamp > now or stamp < now - timedelta(days=14): continue
        selected.append((row, stamp))
    def summarize(days: int) -> dict:
        cohort = [(row, stamp) for row, stamp in selected if stamp >= now - timedelta(days=days)]
        views = sum(number(row, "views", "view_count", "impressions") for row, _ in cohort)
        likes = sum(number(row, "likes", "like_count") for row, _ in cohort)
        replies = sum(number(row, "replies", "comments", "reply_count") for row, _ in cohort)
        shares = sum(number(row, "shares", "share_count") for row, _ in cohort)
        archetypes, formats = Counter(), Counter()
        for row, _ in cohort:
            archetypes[str(row.get("archetype") or "unknown")] += 1
            formats[str(row.get("format") or "unknown")] += 1
        return {"window_days": days, "matched_posts": len(cohort), "matched_creators": len({str(row.get("creator") or "").casefold() for row, _ in cohort}), "total_public_views": round(views, 2), "avg_views": round(views / len(cohort), 2) if cohort else None, "weighted_engagement_per_1000_views": round((likes + 2 * replies + 3 * shares) * 1000 / max(1, views), 4), "reply_rate_per_view": round(replies / max(1, views), 6), "share_rate_per_view": round(shares / max(1, views), 6), "top_archetypes": [{"archetype": key, "samples": count} for key, count in archetypes.most_common(6)], "format_counts": [{"format": key, "samples": count} for key, count in formats.most_common(6)], "evidence_type": "PUBLIC_CONTENT_OBSERVATIONS_NOT_EARNINGS_CAUSALITY"}
    return {"status": "MATCHED_PUBLIC_POSTS_FOUND" if selected else "NO_MATCHING_PUBLIC_POSTS_IN_COLLECTED_SAMPLE", "leaderboard_creator_names_in_public_source": len(targets), "matched_creator_count_14d": len({str(row.get("creator") or "").casefold() for row, _ in selected}), "posts_age_8_to_14_days": sum(1 for _, stamp in selected if now - timedelta(days=14) <= stamp < now - timedelta(days=7)), "seven_day": summarize(7), "fourteen_day": summarize(14), "public_metrics_are_not_earnings": True}
def _window_hypotheses(benchmark: dict) -> list[dict]:
    windows = benchmark.get("rolling_learning_windows") if isinstance(benchmark.get("rolling_learning_windows"), dict) else {}
    result = []
    seen = set()
    for window_name in ("fourteen_day", "seven_day"):
        window = windows.get(window_name) if isinstance(windows.get(window_name), dict) else {}
        for row in window.get("performance_by_archetype", []) if isinstance(window.get("performance_by_archetype"), list) else []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("archetype") or "unknown")
            try:
                n = int(row.get("samples") or 0)
            except (TypeError, ValueError):
                n = 0
            if n < 5 or name == "unknown" or name in seen:
                continue
            seen.add(name)
            result.append({
                "archetype": name,
                "sample_count": n,
                "window_days": int(window.get("window_days") or (14 if window_name == "fourteen_day" else 7)),
                "avg_views": row.get("avg_views"),
                "mean_public_engagement_rate": row.get("mean_public_engagement_rate"),
                "reply_rate": row.get("reply_rate"),
                "avg_replies": row.get("avg_replies"),
                "confidence": str(row.get("confidence") or ("medium" if n >= 10 else "tentative")),
                "evidence_type": "PUBLIC_OBSERVATION_NOT_EARNINGS",
                "usage": "TEST_AS_AN_ORIGINAL_FORMAT_HYPOTHESIS; validate on NIC's own posts",
            })
    result.sort(key=lambda row: (
        float(row.get("reply_rate") or 0),
        float(row.get("mean_public_engagement_rate") or 0),
        float(row.get("sample_count") or 0),
    ), reverse=True)
    return result[:8]


def build_learning_plan(benchmark: dict, patterns: dict, reward_events: list[dict],
                        own_attribution: list[dict] | None = None,
                        own_performance: list[dict] | None = None,
                        now: datetime | None = None, target_usdc: float | None = None,
                        public_examples: list[dict] | None = None,
                        observed_leaderboard_entries: list[dict] | None = None,
                        creator_profile_research: dict | None = None,
                        owner_reported_reward_events: list[dict] | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    target = weekly_target() if target_usdc is None else float(target_usdc)
    windows = benchmark.get("rolling_learning_windows") if isinstance(benchmark.get("rolling_learning_windows"), dict) else {}
    seven = windows.get("seven_day") if isinstance(windows.get("seven_day"), dict) else {}
    fourteen = windows.get("fourteen_day") if isinstance(windows.get("fourteen_day"), dict) else {}
    hypotheses = _window_hypotheses(benchmark)
    reward_summary = collect_verified_rewards(reward_events, now)
    owner_reported_feedback = summarize_owner_reported_reward_feedback(owner_reported_reward_events or [], now)
    own_summary = summarize_own_content(now, own_attribution or [], own_performance or [])
    profile_research = creator_profile_research if isinstance(creator_profile_research, dict) else {}
    researched_profiles = profile_research.get("profiles") if isinstance(profile_research.get("profiles"), list) else []

    # Build a balanced research queue across creator styles and discovery signals.
    # A single high-engagement archetype must not crowd out educational, chart,
    # news, on-chain, macro or discussion-focused creators.
    creator_candidates_by_archetype = defaultdict(list)
    seen_creators = set()
    for window_name, window in (("fourteen_day", fourteen), ("seven_day", seven)):
        for ranking in ("top_by_public_engagement", "top_by_discussion_and_shares", "top_by_median_reach"):
            for creator in window.get(ranking, []) if isinstance(window.get(ranking), list) else []:
                if not isinstance(creator, dict):
                    continue
                cid = str(creator.get("creator_id") or creator.get("creator") or "").strip()
                if not cid or cid in seen_creators or int(creator.get("posts") or 0) < 3:
                    continue
                seen_creators.add(cid)
                archetypes = [str(x).strip() for x in creator.get("dominant_archetypes", []) if str(x).strip() and str(x).lower() != "unknown"]
                item = {
                    "creator": str(creator.get("creator") or "unknown"),
                    "creator_id": cid,
                    "discovery_window": int(window.get("window_days") or (14 if window_name == "fourteen_day" else 7)),
                    "posts_observed": int(creator.get("posts") or 0),
                    "dominant_archetypes": archetypes,
                    "public_engagement_rate": creator.get("mean_public_engagement_rate"),
                    "median_views": creator.get("median_views"),
                    "reply_rate": creator.get("reply_rate"),
                    "share_rate": creator.get("share_rate"),
                    "sample_urls": (creator.get("sample_urls") or [])[:5],
                    "earnings_status": "NOT_PUBLICLY_VERIFIED",
                    "discovery_signal": ranking,
                    "study_objective": "Study repeated structures across multiple posts; do not copy wording or infer private rewards.",
                }
                for archetype_name in (archetypes or ["general"]):
                    creator_candidates_by_archetype[archetype_name].append(item)
    # Round-robin archetypes; stable ordering makes CI and research runs reproducible.
    creator_study_queue = []
    selected_ids = set()
    archetype_names = sorted(creator_candidates_by_archetype)
    while archetype_names and len(creator_study_queue) < 24:
        next_round = []
        for archetype_name in archetype_names:
            candidates = creator_candidates_by_archetype[archetype_name]
            while candidates and candidates[0]["creator_id"] in selected_ids:
                candidates.pop(0)
            if candidates and len(creator_study_queue) < 24:
                item = candidates.pop(0)
                selected_ids.add(item["creator_id"])
                creator_study_queue.append(item)
            if candidates:
                next_round.append(archetype_name)
        archetype_names = next_round

    # Keep public earnings claims as a separate lead list. These claims are
    # useful for discovering creators to study, but they are never treated as
    # verified income or merged into the public-performance ranking.
    public_claim_research = analyze_public_reward_claims(public_examples or [], now)
    # Explicit observations from the authenticated Write-to-Earn page are kept
    # separate from public creator claims and public engagement metrics.
    observed_rows = observed_leaderboard_entries if isinstance(observed_leaderboard_entries, list) else []
    existing_keys = {
        (str(row.get("claimed_creator") or "").casefold(), str(row.get("source_url") or ""), str(row.get("claimed_amount") or ""))
        for row in public_claim_research.get("public_leaderboard_entries", []) if isinstance(row, dict)
    }
    for observed in observed_rows:
        if not isinstance(observed, dict):
            continue
        creator_name = str(observed.get("creator") or "").strip()
        if not creator_name:
            continue
        key = (creator_name.casefold(), str(observed.get("source_url") or ""), str(observed.get("displayed_amount") or ""))
        if key in existing_keys:
            continue
        public_claim_research.setdefault("public_leaderboard_entries", []).append({
            "claimed_creator": creator_name,
            "creator_profile_url": observed.get("creator_profile_url"),
            "claimed_amount": observed.get("displayed_amount"),
            "claimed_currency": observed.get("currency"),
            "rank": observed.get("rank"),
            "source_url": observed.get("source_url"),
            "evidence_ref": observed.get("evidence_ref"),
            "observed_at": observed.get("observed_at"),
            "period_start": observed.get("period_start"),
            "period_end": observed.get("period_end"),
            "earnings_status": "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT",
            "evidence_type": "OBSERVED_WRITE_TO_EARN_LEADERBOARD_ROW",
        })
        existing_keys.add(key)
    leaderboard_creator_public_content = summarize_leaderboard_creator_posts(public_examples or [], public_claim_research.get("public_leaderboard_entries", []), now)
    claim_study_queue = [{
        "creator": row.get("creator", "unknown"),
        "creator_id": row.get("creator_id", ""),
        "sample_urls": row.get("sample_urls", [])[:5],
        "claim_posts_14d": row.get("claim_posts_14d", 0),
        "discovery_window": 14,
        "earnings_status": "UNVERIFIED_PUBLIC_SELF_REPORT",
        "study_objective": "Review public claim context and repeated content formats; never treat the claim as payout proof.",
    } for row in public_claim_research.get("claims", [])[:20]]

    leaderboard_study_queue = [{
        "creator": row.get("claimed_creator", "unknown"),
        "creator_id": "",
        "sample_urls": [row.get("source_url")] if row.get("source_url") else [],
        "source_post_id": row.get("source_post_id"),
        "claimed_amount": row.get("claimed_amount"),
        "claimed_currency": row.get("claimed_currency"),
        "creator_profile_url": row.get("creator_profile_url"),
        "rank": row.get("rank"),
        "evidence_ref": row.get("evidence_ref"),
        "observed_at": row.get("observed_at"),
        "period_start": row.get("period_start"),
        "period_end": row.get("period_end"),
        "discovery_window": 14,
        "earnings_status": row.get("earnings_status") or "PUBLIC_LEADERBOARD_CLAIM_NOT_INDEPENDENTLY_VERIFIED",
        "study_objective": "Study listed creator public posts from the last 7/14 days; do not copy wording or treat listed amounts as independently verified.",
    } for row in public_claim_research.get("public_leaderboard_entries", [])[:50]]

    # Attach observed profile research to matching creator leads, without
    # manufacturing profile links from display names or treating public counts as rewards.
    profile_by_identity = {}
    for profile in researched_profiles:
        if not isinstance(profile, dict):
            continue
        for identity in (profile.get("creator"), profile.get("username"), profile.get("display_name")):
            key = str(identity or "").strip().lstrip("@").casefold()
            if key:
                profile_by_identity.setdefault(key, profile)

    def enrich_creator_row(row: dict) -> None:
        key = str(row.get("creator") or "").strip().lstrip("@").casefold()
        profile = profile_by_identity.get(key)
        if not profile:
            return
        row["creator_profile_url"] = profile.get("creator_profile_url")
        row["profile_research_status"] = profile.get("posts_status") or "PROFILE_RESEARCHED"
        row["profile_posts_7d"] = profile.get("posts_7d", 0)
        row["profile_posts_14d"] = profile.get("posts_14d", 0)
        row["recent_post_samples"] = profile.get("recent_post_samples", [])
        row["creator_username"] = profile.get("username")

    for row in creator_study_queue:
        enrich_creator_row(row)
    for row in leaderboard_study_queue:
        enrich_creator_row(row)

    benchmark_state = str(benchmark.get("status") or "UNKNOWN")
    older_count = int((fourteen.get("coverage") or {}).get("posts_age_8_to_14_days") or 0)
    public_feed_coverage_status = "FULL_7_AND_14_DAY_COVERAGE" if older_count > 0 else "14_DAY_SAMPLE_GAP_KEEP_COLLECTING"
    profile_posts_7d = int(profile_research.get("posts_collected_7d") or 0)
    profile_posts_8_to_14d = int(profile_research.get("posts_collected_8_to_14d") or 0)
    profile_coverage_observed = (
        bool(profile_research.get("seven_day_coverage_observed"))
        and bool(profile_research.get("fourteen_day_coverage_observed"))
        and profile_posts_7d > 0 and profile_posts_8_to_14d > 0
    )
    coverage_status = (
        "FULL_7_AND_14_DAY_PROFILE_COVERAGE" if profile_coverage_observed
        else public_feed_coverage_status
    )
    return {
        "schema": "NIC-SQUARE-EARNINGS-LEARNING-1.0",
        "generated_at": now.isoformat(),
        "mission": "Maximize genuine Binance Square creator earnings through better original content, meaningful engagement, and exact reward attribution.",
        "weekly_earnings_goal": {
            "target_usdc": target,
            "goal_type": "OPTIMIZATION_TARGET_NOT_FORECAST",
            "guaranteed": False,
            "actual_verified_usdc_7d": reward_summary["verified_usdc_7d"],
            "actual_status": reward_summary["verified_usdc_7d_status"],
        },
        "current_program_mechanics": {
            "source_url": OFFICIAL_PROGRAM_URL,
            "source_account": "Binance Square Official",
            "rules_last_checked": now.date().isoformat(),
            "relevant_trade_attribution": "Use an accurate relevant cashtag or genuine Square-native trading widget when a post discusses a tradeable asset; eligible reader trades can generate trading-fee commission.",
            "trade_commission_reward_window_days": 7,
            "engagement_reward_window_days": 30,
            "engagement_bonus_settlement_period_days": 7,
            "channel_breakdown_available_in_creator_center": ["text", "live_streams", "chats"],
            "own_post_learning_rule": "Join channel and per-content reward records to exact canonical post IDs; use the 7-day trade-attribution window and 30-day genuine-engagement window separately.",
            "engagement_bonus_effective_at": "2026-10-19T00:00:00+00:00",
            "rules_change_cohort_policy": "Keep 2026-10-12 through 2026-10-18 under previous rules; evaluate posts published from 2026-10-19 separately under the new engagement-bonus rules.",
            "engagement_bonus_signal": "Genuine high-quality engagement; Binance explicitly names comments, likes and follows, and platform weighting is discretionary rather than a fixed payout per interaction.",
            "format_reward_map": {
                "short_text_posts": "Eligible for text trading commission and may receive weekly engagement bonus.",
                "long_articles": "Eligible text content; may receive weekly engagement bonus.",
                "videos": "Eligible content format; may receive weekly engagement bonus when qualifying.",
                "livestreams": "Basic commission; weekly bonus is limited to the top 100 creators by weekly basic commission (ranks 1-30: 30%, ranks 31-100: 10%).",
                "chats": "Basic commission; no text engagement bonus listed for chats."
            },
            "active_autonomous_format": "text_posts_and_article_style_posts",
            "format_expansion_policy": "Do not claim to produce or publish video/livestream content until the corresponding production and moderation workflow exists.",

            "anti_abuse_rule": "No scripted, coordinated, bought or manufactured engagement; no engagement bait presented as substance.",
            "program_note": "Eligibility, qualifying actions and reward decisions are controlled by Binance; content quality and engagement do not guarantee a payout.",
        },
        "research_coverage": {
            "status": coverage_status,
            "public_feed_status": public_feed_coverage_status,
            "profile_research_status": str(profile_research.get("status") or "NOT_RUN"),
            "profile_coverage_observed": profile_coverage_observed,
            "profile_posts_7d": profile_posts_7d,
            "profile_posts_8_to_14d": profile_posts_8_to_14d,
            "benchmark_status": benchmark_state,
            "collected_posts_last_run": int(benchmark.get("public_posts_collected_this_run") or 0),
            "public_posts_retained": int(benchmark.get("public_posts_observed") or 0),
            "distinct_public_creators_retained": int(benchmark.get("distinct_public_creators") or 0),
            "seven_day_dated_posts": int(seven.get("dated_posts") or 0),
            "fourteen_day_dated_posts": int(fourteen.get("dated_posts") or 0),
            "posts_age_8_to_14_days": older_count,
            "metric_history": benchmark.get("metric_history") or {},
            "earnings_claims_verified_from_public_creator_metrics": 0,
            "public_views_or_engagement_are_earnings_evidence": False,
        },
        "creator_study_queue": creator_study_queue,
        "creator_research_coverage": {
            "window_days": [7, 14],
            "selected_creator_count": len(creator_study_queue),
            "represented_archetypes": sorted({name for creator in creator_study_queue for name in creator.get("dominant_archetypes", [])}),
            "selection_signals": ["public_engagement", "discussion_and_shares", "median_reach"],
            "selection_policy": "Archetype-stratified round-robin; public performance is not proof of earnings.",
        },
        "creator_profile_research": {
            "status": str(profile_research.get("status") or "NOT_RUN"),
            "public_only": bool(profile_research.get("public_only", True)),
            "authenticated_session_used": bool(profile_research.get("authenticated_session_used", False)),
            "candidates": int(profile_research.get("candidate_count") or 0),
            "profiles_resolved": int(profile_research.get("profiles_resolved") or 0),
            "profile_resolution_failures": int(profile_research.get("profile_resolution_failures") or 0),
            "posts_collected_7d": int(profile_research.get("posts_collected_7d") or 0),
            "posts_collected_8_to_14d": int(profile_research.get("posts_collected_8_to_14d") or 0),
            "posts_collected_14d": int(profile_research.get("posts_collected_14d") or 0),
            "seven_day_coverage_observed": bool(profile_research.get("seven_day_coverage_observed", False)),
            "fourteen_day_coverage_observed": bool(profile_research.get("fourteen_day_coverage_observed", False)),
            "public_metrics_are_not_earnings": True,
        },
        "creator_profile_study_queue": [{
            "creator": profile.get("creator"),
            "username": profile.get("username"),
            "creator_profile_url": profile.get("creator_profile_url"),
            "discovery_source": profile.get("discovery_source"),
            "earnings_status": profile.get("earnings_status") or "PUBLIC_RESEARCH_LEAD_NOT_VERIFIED",
            "posts_7d": profile.get("posts_7d", 0),
            "posts_14d": profile.get("posts_14d", 0),
            "recent_post_samples": profile.get("recent_post_samples", [])[:10],
            "evidence_type": "PUBLIC_PROFILE_RESEARCH_NOT_EARNINGS",
        } for profile in researched_profiles if isinstance(profile, dict)],
        "public_self_reported_earnings_claims": public_claim_research,
        "self_reported_earnings_creator_study_queue": claim_study_queue,        "public_earnings_leaderboard_study_queue": leaderboard_study_queue,
        "leaderboard_creator_public_content": leaderboard_creator_public_content,
        "leaderboard_research_coverage": {
            "window_days": [7, 14],
            "public_leaderboard_entries_found": len(public_claim_research.get("public_leaderboard_entries", [])),
            "observed_wte_leaderboard_entries_count": len([row for row in observed_rows if isinstance(row, dict)]),
            "creator_names_queued_for_post_study": len(leaderboard_study_queue),
            "amounts_are_not_payout_proof": True,
        },
        "observed_wte_leaderboard_entries_count": len([row for row in observed_rows if isinstance(row, dict)]),
        "best_public_format_hypotheses": hypotheses,
        "own_account_performance": own_summary,
        "historical_own_account_baseline": patterns.get("our_baseline") if isinstance(patterns.get("our_baseline"), dict) else {},
        "verified_reward_evidence": reward_summary,
        "owner_reported_reward_feedback": owner_reported_feedback,
        "creator_format_strategy": {
            "source": "https://www.binance.com/en/support/announcement/detail/d9c84b68e9ab4ef29bee0cc53dfdabd2",
            "priority": [
                {"format": "evidence-led short text post", "purpose": "one timely insight, mechanism, reader payoff, counterpoint and one answerable question"},
                {"format": "article-style text post", "purpose": "original explainers, comparisons, research notes and outcome follow-ups with clear structure"},
                {"format": "case study / accountability follow-up", "purpose": "show what changed, what was learned and what evidence would falsify the thesis"},
                {"format": "video or livestream", "purpose": "future expansion only after a validated production workflow exists; never pretend a text draft is video"}
            ],
            "engagement_design": "Optimize for genuine comments, likes and follows by being useful and specific; do not manufacture engagement or imply a guaranteed reward.",
            "experiment_rule": "Compare format and hook variants against NIC's own baseline, while keeping the 2026-10-19 reward-rule cohort separate.",
            "payout_rule": "No public engagement metric or creator-reported amount is treated as verified payout evidence."
        },
        "recommended_content_playbook": [
            "Lead with one timely, specific insight that the evidence supports; avoid generic ticker-first templates.",
            "Explain the mechanism and reader payoff, not just a price move or copied headline.",
            "For a relevant tradeable asset, verify the asset identity and use an accurate cashtag or real Square-native widget where appropriate for attribution.",
            "Invite genuine discussion with one specific, answerable question; never solicit fake, coordinated or repetitive engagement.",
            "Favor posts with a clear differentiator, primary-source context, practical implications and an honest counterpoint.",
            "Use charts only when symbol, timeframe, market data and visual labels are verified and materially help the reader.",
            "Follow up with outcome or new evidence within the post's useful reward window; do not repeat the same setup without new information.",
            "Test one meaningful format/hook variable at a time and promote patterns only after repeated observations against NIC's own baseline.",
            "Never claim an archetype earned money unless exact-post reward evidence proves that relationship; public metrics remain directional.",
        ],
        "learning_policy": {
            "rolling_windows_days": [7, 14],
            "minimum_creator_posts_for_study": 3,
            "minimum_archetype_samples_for_hypothesis": 5,
            "learn_patterns_not_text": True,
            "update_bounded_priors_only": True,
            "own_verified_rewards_outweigh_public_metrics": True,
            "do_not_infer_private_creator_earnings": True,
            "do_not_guarantee_weekly_target": True,
            "automatic_posting_enabled": bool(load_json(ROOT / "nic_publication_policy.json", {}).get("editorial_auto_publication_enabled") is True),
        },
    }


def build_learning_memory_entry(plan: dict, now: datetime) -> dict:
    """Persist small audit metrics for autonomous learning across daily cycles."""
    owner = plan.get("owner_reported_reward_feedback") if isinstance(plan.get("owner_reported_reward_feedback"), dict) else {}
    owner_7d = owner.get("7_day") if isinstance(owner.get("7_day"), dict) else {}
    coverage = plan.get("research_coverage") if isinstance(plan.get("research_coverage"), dict) else {}
    profile = plan.get("creator_profile_research") if isinstance(plan.get("creator_profile_research"), dict) else {}
    weekly = plan.get("weekly_earnings_goal") if isinstance(plan.get("weekly_earnings_goal"), dict) else {}
    verified = plan.get("verified_reward_evidence") if isinstance(plan.get("verified_reward_evidence"), dict) else {}
    hypotheses = plan.get("best_public_format_hypotheses") if isinstance(plan.get("best_public_format_hypotheses"), list) else []
    creator_queue = plan.get("creator_study_queue") if isinstance(plan.get("creator_study_queue"), list) else []
    leaderboard_queue = plan.get("public_earnings_leaderboard_study_queue") if isinstance(plan.get("public_earnings_leaderboard_study_queue"), list) else []
    return {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "coverage_status": str(coverage.get("status") or "UNKNOWN"),
        "profile_research_status": str(profile.get("status") or "NOT_RUN"),
        "creator_profiles_resolved": int(profile.get("profiles_resolved") or 0),
        "profile_posts_7d": int(profile.get("posts_collected_7d") or 0),
        "profile_posts_8_to_14d": int(profile.get("posts_collected_8_to_14d") or 0),
        "weekly_goal_usdc": weekly.get("target_usdc"),
        "verified_usdc_7d": weekly.get("actual_verified_usdc_7d"),
        "verified_reward_events_7d": int(verified.get("accepted_unique_reward_events_7d") or 0),
        "owner_reported_usdc_7d": owner_7d.get("reported_usdc"),
        "owner_reported_reward_events_7d": int(owner_7d.get("reported_event_count") or 0),
        "owner_reported_reward_posts_7d": int(owner_7d.get("post_count") or 0),
        "owner_reported_feedback_status": str(owner.get("status") or "NO_OWNER_REPORTED_FEEDBACK"),
        "creator_study_count": len(creator_queue),
        "leaderboard_creator_study_count": len(leaderboard_queue),
        "hypothesis_archetypes": [str(row.get("archetype") or "unknown")[:60] for row in hypotheses if isinstance(row, dict)],
        "owner_reported_feedback_is_not_verified": True,
    }


def build_autonomy_readiness(plan: dict, public_wte_claim_discovery: dict | None = None,
                             publication_policy: dict | None = None) -> dict:
    """Expose exactly which autonomy capabilities are ready and which lack evidence/source access."""
    discovery = public_wte_claim_discovery if isinstance(public_wte_claim_discovery, dict) else {}
    policy = publication_policy if isinstance(publication_policy, dict) else {}
    coverage = plan.get("research_coverage") if isinstance(plan.get("research_coverage"), dict) else {}
    profile = plan.get("creator_profile_research") if isinstance(plan.get("creator_profile_research"), dict) else {}
    owner = plan.get("owner_reported_reward_feedback") if isinstance(plan.get("owner_reported_reward_feedback"), dict) else {}
    owner7 = owner.get("7_day") if isinstance(owner.get("7_day"), dict) else {}
    verified = plan.get("verified_reward_evidence") if isinstance(plan.get("verified_reward_evidence"), dict) else {}
    # Only observations explicitly ingested from the observed WTE input count
    # as leaderboard rows. Public self-reported claims in the study queue do not.
    observed_count = int(plan.get("observed_wte_leaderboard_entries_count") or 0)
    profiles_ready = (
        str(profile.get("status") or "") == "PROFILE_RESEARCH_COMPLETE"
        and bool(profile.get("seven_day_coverage_observed"))
        and bool(profile.get("fourteen_day_coverage_observed"))
        and int(profile.get("profiles_resolved") or 0) > 0
    )
    verified_rewards = int(verified.get("accepted_unique_reward_events_7d") or 0)
    claims_count = int(discovery.get("retained_recent_claim_post_count") or 0)
    corpus_rows = int(discovery.get("public_corpus_rows_checked") or 0)
    blockers = []

    if observed_count == 0:
        blockers.append({
            "id": "other_creator_paid_reward_source",
            "severity": "critical",
            "status": "BLOCKED_NO_AUTHORIZED_SOURCE",
            "capability_affected": "Select and learn from creators ranked by actual weekly Write-to-Earn payouts (e.g. $500+).",
            "evidence": "No observed Write-to-Earn leaderboard entries are available in the current learning input; public post metrics and self-reported claims are not payout proof.",
            "required_resolution": "Connect an officially supported, authorized read-only source or a permitted structured export. Do not bypass authentication or replay browser fingerprints.",
        })
    if verified_rewards == 0:
        blockers.append({
            "id": "own_post_reward_attribution",
            "severity": "critical",
            "status": "BLOCKED_NO_VERIFIED_POST_LINKED_REWARD",
            "capability_affected": "Prove which of NIC's own posts generated a paid reward and calibrate content decisions against confirmed outcomes.",
            "evidence": "The verified ledger contains no accepted exact-post paid reward event. Owner-reported feedback is kept separately and is not independently verified.",
            "owner_reported_events_7d": int(owner7.get("reported_event_count") or 0),
            "owner_reported_usdc_7d": owner7.get("reported_usdc"),
            "required_resolution": "Add post-linked reward evidence from an authorized account export/notification flow and preserve its timestamped evidence reference.",
        })
    if not profiles_ready:
        blockers.append({
            "id": "creator_profile_7_14_day_coverage",
            "severity": "high",
            "status": "INCOMPLETE",
            "capability_affected": "Study a rotating set of public creators across both 7-day and 14-day windows.",
            "profile_research_status": str(profile.get("status") or "NOT_RUN"),
            "required_resolution": "Restore public endpoint access and maintain dated profile-post coverage; do not fill missing dates by guessing.",
        })
    if claims_count == 0:
        blockers.append({
            "id": "public_reward_claim_leads",
            "severity": "warning",
            "status": "NO_RECENT_PUBLIC_CLAIMS_FOUND",
            "capability_affected": "Discover public creators' own recent reward claims as unverified research leads.",
            "public_corpus_rows_checked": corpus_rows,
            "discovery_status": str(discovery.get("status") or "NOT_RUN"),
            "required_resolution": "Continue scanning the public feed; treat any discovered creator amount as self-reported unless independently supported.",
        })

    enabled = policy.get("editorial_auto_publication_enabled") is True
    human_review = policy.get("requires_human_review_for_editorial") is True
    return {
        "schema": "NIC-AUTONOMY-READINESS-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PUBLIC_RESEARCH_READY_PRIVATE_REWARD_SOURCE_BLOCKED" if profiles_ready and observed_count == 0
                  else "PARTIAL_AUTONOMY_BLOCKED" if blockers else "RESEARCH_READY_REQUIRES_REVIEW",
        "full_autonomy_proven": False,
        "capabilities": {
            "public_creator_profile_research": {
                "status": "READY" if profiles_ready else "INCOMPLETE",
                "profiles_resolved": int(profile.get("profiles_resolved") or 0),
                "posts_7d": int(profile.get("posts_collected_7d") or 0),
                "posts_8_to_14d": int(profile.get("posts_collected_8_to_14d") or 0),
            },
            "public_reward_claim_discovery": {
                "status": str(discovery.get("status") or "NOT_RUN"),
                "recent_claim_posts_found": claims_count,
                "public_corpus_rows_checked": corpus_rows,
                "self_reports_are_unverified": True,
            },
            "other_creator_weekly_reward_source": {
                "status": "CONNECTED_OBSERVATIONS_PRESENT" if observed_count else "BLOCKED_NO_AUTHORIZED_SOURCE",
                "observed_entries_in_current_study_queue": observed_count,
                "independent_payout_verification_available": False,
            },
            "own_post_reward_attribution": {
                "status": "VERIFIED_EVENTS_PRESENT" if verified_rewards else "BLOCKED_NO_VERIFIED_POST_LINKED_REWARD",
                "verified_events_7d": verified_rewards,
                "owner_reported_events_7d": int(owner7.get("reported_event_count") or 0),
                "owner_reported_usdc_7d": owner7.get("reported_usdc"),
                "owner_reports_are_not_verified": True,
            },
            "automatic_publication": {
                "enabled_by_policy": enabled,
                "human_review_required": human_review,
                "status": "DISABLED_BY_POLICY" if not enabled else (
                    "BLOCKED_HUMAN_REVIEW_REQUIRED" if human_review else "POLICY_ENABLED_GUARDED_QUALITY_GATES_REQUIRED"
                ),
                "publication_authorized_by_this_report": False,
            },
        },
        "critical_blocker_count": sum(1 for row in blockers if row.get("severity") == "critical"),
        "blockers": blockers,
        "policy": {
            "public_metrics_are_not_payout_evidence": True,
            "no_unauthorized_private_dashboard_access": True,
            "automatic_publication_requires_current_cycle_quality_gates": True,
            "no_auto_publish_without_current_cycle_authorization": True,
        },
        "next_action": "Keep guarded editorial publication running only when every current-cycle gate passes; connect an officially supported, authorized read-only reward source or permitted export for verified creator-payout learning, and preserve exact-post own reward evidence.",
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    benchmark = load_json(BENCHMARK, {})
    patterns = load_json(PATTERNS, {})
    rewards = load_jsonl(REWARD_EVENTS)
    owner_reported_rewards = load_jsonl(OWNER_REPORTED_REWARDS)
    attribution = load_jsonl(ATTRIBUTION)
    performance = load_jsonl(PERFORMANCE)
    examples = load_json(EXAMPLES, [])
    if not isinstance(examples, list):
        examples = []
    leaderboard_input_path = INTEL / "wte_leaderboard_observations.json"
    leaderboard_input = load_json(leaderboard_input_path, {"entries": []})
    normalized_leaderboard = normalize_observations(leaderboard_input, now)
    observed_leaderboard_entries = normalized_leaderboard.get("entries", [])
    (INTEL / "wte_leaderboard_observed.json").write_text(
        json.dumps(normalized_leaderboard, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8"
    )
    profile_research = load_json(INTEL / "nic_square_profile_research.json", {})
    if not isinstance(profile_research, dict):
        profile_research = {}
    public_wte_discovery = load_json(INTEL / "public_wte_claim_discoveries.json", {})
    if not isinstance(public_wte_discovery, dict):
        public_wte_discovery = {}
    publication_policy = load_json(ROOT / "nic_publication_policy.json", {})
    if not isinstance(publication_policy, dict):
        publication_policy = {}
    plan = build_learning_plan(
        benchmark, patterns, rewards, attribution, performance, now,
        public_examples=examples, observed_leaderboard_entries=observed_leaderboard_entries,
        creator_profile_research=profile_research, owner_reported_reward_events=owner_reported_rewards,
    )
    readiness = build_autonomy_readiness(plan, public_wte_discovery, publication_policy)
    plan["autonomy_readiness"] = readiness
    INTEL.mkdir(parents=True, exist_ok=True)
    (INTEL / "nic_autonomy_readiness.json").write_text(
        json.dumps(readiness, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    previous = load_json(MEMORY, {"history": []})
    history = previous.get("history") if isinstance(previous.get("history"), list) else []
    today = now.date().isoformat()
    history = [row for row in history if isinstance(row, dict) and str(row.get("date") or "") != today]
    history.append(build_learning_memory_entry(plan, now))
    memory = {"schema": "NIC-SQUARE-EARNINGS-LEARNING-MEMORY-1.0", "updated_at": now.isoformat(), "history": history[-30:]}
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "schema": plan["schema"],
        "generated_at": now.isoformat(),
        "status": "READY" if benchmark.get("status") == "PUBLIC_BENCHMARKS_AVAILABLE" else "COLLECTING_PUBLIC_CREATOR_RESEARCH",
        "weekly_goal_usdc": plan["weekly_earnings_goal"]["target_usdc"],
        "public_creator_study_queue": len(plan["creator_study_queue"]),
        "public_self_reported_earnings_claim_creators": plan["public_self_reported_earnings_claims"]["distinct_claiming_creators"],
        "public_archetype_hypotheses": len(plan["best_public_format_hypotheses"]),
        "verified_reward_events_7d": plan["verified_reward_evidence"]["accepted_unique_reward_events_7d"],
        "verified_usdc_7d": plan["weekly_earnings_goal"]["actual_verified_usdc_7d"],
        "owner_reported_usdc_7d": plan["owner_reported_reward_feedback"]["7_day"]["reported_usdc"],
        "owner_reported_events_7d": plan["owner_reported_reward_feedback"]["7_day"]["reported_event_count"],
        "owner_reported_feedback_status": plan["owner_reported_reward_feedback"]["status"],
        "coverage_status": plan["research_coverage"]["status"],
        "creator_profiles_resolved": plan["creator_profile_research"]["profiles_resolved"],
        "profile_posts_collected_14d": plan["creator_profile_research"]["posts_collected_14d"],
        "profile_research_status": plan["creator_profile_research"]["status"],
        "autonomy_status": plan["autonomy_readiness"]["status"],
        "autonomy_critical_blockers": plan["autonomy_readiness"]["critical_blocker_count"],
        "autonomy_blocker_ids": [row["id"] for row in plan["autonomy_readiness"]["blockers"]],
        "autopublish_enabled": plan["autonomy_readiness"]["capabilities"]["automatic_publication"]["enabled_by_policy"],
        "public_metrics_are_not_earnings": True,
        "output": str(OUT.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
