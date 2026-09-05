"""Creator 7.0 autonomous mission and economic decision engine.

This is the strategic layer above content generation. It does not invent revenue:
it separates verified revenue from proxies and chooses the next action from the
best available evidence. The mission is persistent through data/intelligence.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
CADENCE = ROOT / "data/live/autonomous_cadence_6.json"
IDENTITY = ROOT / "data/live/creator_identity_6_6.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
GROWTH = ROOT / "data/intelligence/creator_growth_system.json"
LOG = ROOT / "analytics/publication_log.jsonl"
STATE = ROOT / "data/intelligence/creator_mission_7.json"
OUT = ROOT / "data/live/creator_mission_7.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def recent_publications(limit: int = 30) -> list[dict]:
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-250:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("status") == "PUBLISHED_AUTONOMOUSLY":
            rows.append(row)
    return rows[-limit:]


def main() -> None:
    now = datetime.now(timezone.utc)
    ranking = load(RANKING)
    cadence = load(CADENCE)
    identity = load(IDENTITY)
    feedback = load(FEEDBACK)
    growth = load(GROWTH)
    previous = load(STATE)
    posts = recent_publications()

    selected = ranking.get("selected") or {}
    if not isinstance(selected, dict):
        selected = {}

    score = num(selected.get("ranker_score") or selected.get("identity_score") or selected.get("score"))
    category = str(selected.get("category") or selected.get("lane") or "").lower()
    symbol = str(selected.get("symbol") or "").upper()
    title = str(selected.get("news_title") or selected.get("title") or "").strip()

    # Mission state is a 7-day sprint, renewed automatically after expiry.
    old_start = str(previous.get("sprint", {}).get("started_at") or "")
    try:
        start = datetime.fromisoformat(old_start.replace("Z", "+00:00"))
    except Exception:
        start = now
    if now - start >= timedelta(days=7):
        start = now
        previous = {}
    end = start + timedelta(days=7)

    verified_revenue = num(previous.get("verified_revenue_usdc"))
    verified_events = int(num(previous.get("verified_revenue_events")))
    # These are deliberately proxies, not claimed revenue.
    total_views = sum(num(p.get("views")) for p in posts)
    total_likes = sum(num(p.get("likes")) for p in posts)
    total_comments = sum(num(p.get("comments")) for p in posts)
    total_shares = sum(num(p.get("shares")) for p in posts)
    follower_delta = sum(num(p.get("followers_gained")) for p in posts)

    history_categories = [str(p.get("category") or "").lower() for p in posts[-8:]]
    history_symbols = [str(p.get("symbol") or "").upper() for p in posts[-8:]]
    same_category = category and history_categories.count(category) >= 3
    same_symbol = symbol and history_symbols.count(symbol) >= 3

    quality_signal = num(feedback.get("overall_quality") or feedback.get("quality_score") or feedback.get("score"))
    growth_score = num(growth.get("growth_score") or growth.get("score"))

    # Strategic action: money first, but never at the cost of spam or unsupported claims.
    if verified_revenue > 0:
        primary_goal = "increase_verified_monetization"
    elif score >= 95:
        primary_goal = "capture_high_intent_opportunity"
    elif title and category in {"breaking_news", "news_market_impact", "creator_signal_outcome"}:
        primary_goal = "build_trust_and_intent_from_fresh_information"
    else:
        primary_goal = "run_a_learning_experiment"

    if same_category and same_symbol:
        action = "PIVOT"
        reason = "recent content is concentrated on the same category and asset"
    elif score >= 110:
        action = "ACT_NOW"
        reason = "exceptionally strong opportunity"
    elif score >= 78:
        action = "ACT_IF_FRESH"
        reason = "strong opportunity with sufficient quality"
    elif score >= 60:
        action = "RESEARCH_MORE"
        reason = "promising but not yet strong enough for aggressive publication"
    else:
        action = "WAIT"
        reason = "no sufficiently strong opportunity"

    # Platform economics: Write to Earn is tied to eligible reader trades after
    # interaction, so cashtag/chart eligibility is an optimization signal, not
    # proof of income. Actual revenue must be supplied by verified account data.
    monetization_design = {
        "verified_revenue_usdc": verified_revenue,
        "verified_revenue_events": verified_events,
        "revenue_is_verified": verified_revenue > 0 or verified_events > 0,
        "eligible_content_should_use_relevant_cashtag_or_trading_widget": True,
        "avoid_spam_or_duplicate_content": True,
        "do_not_claim_revenue_from_views_or_likes": True,
        "do_not_fabricate_reader_trades": True,
    }

    experiments = [
        "fresh_event_to_market_impact",
        "one_chart_one_decision",
        "data_surprise_vs_price",
        "contrarian_risk_test",
        "creator_call_outcome",
        "high_intent_watchlist",
    ]
    used = {str(p.get("format") or "") for p in posts[-10:]}
    next_experiment = next((x for x in experiments if x not in used), experiments[0])

    mission = {
        "version": "7.0",
        "generated_at": now.isoformat(),
        "mission": "build legitimate, durable Binance Square income by creating high-trust content that earns real reader action",
        "sprint": {
            "started_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "days_remaining": max(0, (end - now).days),
        },
        "priority_order": [
            "verified_monetization",
            "reader_value_and_trust",
            "audience_growth",
            "learning_rate",
            "creative_variation",
        ],
        "decision": {
            "action": action,
            "reason": reason,
            "primary_goal": primary_goal,
            "selected_score": score,
            "selected_category": category,
            "selected_symbol": symbol or None,
            "selected_story": title or None,
            "next_experiment": next_experiment,
        },
        "economic_state": monetization_design,
        "observed_proxies": {
            "recent_published_posts": len(posts),
            "recent_views_proxy": total_views,
            "recent_likes_proxy": total_likes,
            "recent_comments_proxy": total_comments,
            "recent_shares_proxy": total_shares,
            "recent_follower_delta_proxy": follower_delta,
            "quality_signal": quality_signal,
            "growth_signal": growth_score,
        },
        "agency_rules": [
            "choose opportunity rather than obey a fixed posting clock",
            "wait when evidence is weak",
            "interrupt normal cadence for genuinely strong fresh opportunities",
            "pivot when recent output becomes repetitive",
            "prefer evidence over narrative convenience",
            "learn from outcomes before changing strategy",
            "never invent revenue, trades, personal experience, or market facts",
        ],
        "human_safety_boundary": "strategic autonomy does not authorize manipulation, spam, fabricated evidence, or financial transactions",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(mission, indent=2, ensure_ascii=False), encoding="utf-8")
    STATE.write_text(json.dumps(mission, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(mission, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
