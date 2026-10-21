"""Monetization-focused NIC learning from rolling public creator research.

The target is an optimization goal, not a promise. Public creator metrics are not
earnings proof; only exact-post, source-backed reward events count as verified pay.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from src.nic_reward_evidence import is_verified_reward_event, canonical_post_id, reward_event_rejection_reasons
except ModuleNotFoundError:
    from nic_reward_evidence import is_verified_reward_event, canonical_post_id, reward_event_rejection_reasons

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
INTEL = ROOT / "data/intelligence"
LIVE = ROOT / "data/live"
BENCHMARK = INTEL / "square_creator_benchmark.json"
PATTERNS = INTEL / "creator_patterns.json"
REWARD_EVENTS = ANALYTICS / "wte_reward_events.jsonl"
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
            sample = {
                "views": number(perf, "views", "view_count", "impressions"),
                "likes": number(perf, "likes", "like_count"),
                "replies": number(perf, "comments", "replies", "reply_count"),
                "shares": number(perf, "shares", "share_count"),
            }
            eligible.append(sample)
            groups[category].append(sample)
        def aggregate(samples: list[dict]) -> dict:
            n = len(samples)
            views = sum(x["views"] for x in samples)
            likes = sum(x["likes"] for x in samples)
            replies = sum(x["replies"] for x in samples)
            shares = sum(x["shares"] for x in samples)
            return {
                "posts": n,
                "avg_views": round(views / n, 2) if n else None,
                "total_views": round(views, 2),
                "reply_rate_per_view": round(replies / max(1, views), 6),
                "share_rate_per_view": round(shares / max(1, views), 6),
                "weighted_engagement_per_1000_views": round((likes + 2 * replies + 3 * shares) * 1000 / max(1, views), 4),
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
                        now: datetime | None = None, target_usdc: float | None = None) -> dict:
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
    own_summary = summarize_own_content(now, own_attribution or [], own_performance or [])

    creator_study_queue = []
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
                creator_study_queue.append({
                    "creator": str(creator.get("creator") or "unknown"),
                    "creator_id": cid,
                    "discovery_window": int(window.get("window_days") or (14 if window_name == "fourteen_day" else 7)),
                    "posts_observed": int(creator.get("posts") or 0),
                    "dominant_archetypes": creator.get("dominant_archetypes", []),
                    "public_engagement_rate": creator.get("mean_public_engagement_rate"),
                    "median_views": creator.get("median_views"),
                    "reply_rate": creator.get("reply_rate"),
                    "share_rate": creator.get("share_rate"),
                    "sample_urls": (creator.get("sample_urls") or [])[:5],
                    "earnings_status": "NOT_PUBLICLY_VERIFIED",
                    "study_objective": "Study repeatable structures across multiple posts; do not copy text or infer private rewards.",
                })
                if len(creator_study_queue) >= 24:
                    break
            if len(creator_study_queue) >= 24:
                break
        if len(creator_study_queue) >= 24:
            break

    benchmark_state = str(benchmark.get("status") or "UNKNOWN")
    older_count = int((fourteen.get("coverage") or {}).get("posts_age_8_to_14_days") or 0)
    coverage_status = "FULL_7_AND_14_DAY_COVERAGE" if older_count > 0 else "14_DAY_SAMPLE_GAP_KEEP_COLLECTING"
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
            "text_content_engagement_bonus_window_days": 30,
            "engagement_bonus_signal": "Genuine quality engagement including comments, likes, follows and shares; platform weights may vary.",
            "anti_abuse_rule": "No scripted, coordinated, bought or manufactured engagement; no engagement bait presented as substance.",
            "program_note": "Eligibility, qualifying actions and reward decisions are controlled by Binance; content quality and engagement do not guarantee a payout.",
        },
        "research_coverage": {
            "status": coverage_status,
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
        "best_public_format_hypotheses": hypotheses,
        "own_account_performance": own_summary,
        "historical_own_account_baseline": patterns.get("our_baseline") if isinstance(patterns.get("our_baseline"), dict) else {},
        "verified_reward_evidence": reward_summary,
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
            "automatic_posting_enabled": False,
        },
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    benchmark = load_json(BENCHMARK, {})
    patterns = load_json(PATTERNS, {})
    rewards = load_jsonl(REWARD_EVENTS)
    attribution = load_jsonl(ATTRIBUTION)
    performance = load_jsonl(PERFORMANCE)
    plan = build_learning_plan(benchmark, patterns, rewards, attribution, performance, now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    previous = load_json(MEMORY, {"history": []})
    history = previous.get("history") if isinstance(previous.get("history"), list) else []
    today = now.date().isoformat()
    history = [row for row in history if isinstance(row, dict) and str(row.get("date") or "") != today]
    history.append({
        "date": today,
        "generated_at": now.isoformat(),
        "coverage_status": plan["research_coverage"]["status"],
        "weekly_goal_usdc": plan["weekly_earnings_goal"]["target_usdc"],
        "verified_usdc_7d": plan["weekly_earnings_goal"]["actual_verified_usdc_7d"],
        "creator_study_count": len(plan["creator_study_queue"]),
        "hypothesis_archetypes": [row["archetype"] for row in plan["best_public_format_hypotheses"]],
    })
    memory = {"schema": "NIC-SQUARE-EARNINGS-LEARNING-MEMORY-1.0", "updated_at": now.isoformat(), "history": history[-30:]}
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "schema": plan["schema"],
        "generated_at": now.isoformat(),
        "status": "READY" if benchmark.get("status") == "PUBLIC_BENCHMARKS_AVAILABLE" else "COLLECTING_PUBLIC_CREATOR_RESEARCH",
        "weekly_goal_usdc": plan["weekly_earnings_goal"]["target_usdc"],
        "public_creator_study_queue": len(plan["creator_study_queue"]),
        "public_archetype_hypotheses": len(plan["best_public_format_hypotheses"]),
        "verified_reward_events_7d": plan["verified_reward_evidence"]["accepted_unique_reward_events_7d"],
        "verified_usdc_7d": plan["weekly_earnings_goal"]["actual_verified_usdc_7d"],
        "coverage_status": plan["research_coverage"]["status"],
        "public_metrics_are_not_earnings": True,
        "output": str(OUT.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
