"""Creator 7.0 autonomous economic mission brain.

This is a decision layer, not a money guarantee. It turns available market,
news, campaign and historical performance evidence into a seven-day operating
mission, ranks monetization opportunities, and chooses whether the creator
should pursue reach, reader-action, campaign relevance, learning or rest.

Revenue is treated as verified only when the repository contains actual
monetization evidence. Views/likes/comments/clicks are proxies, never revenue.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
NEWS = ROOT / "data/live/news_snapshot.json"
PERF = ROOT / "data/intelligence/performance_feedback.json"
GROWTH = ROOT / "data/intelligence/creator_growth.json"
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/autonomous_economic_brain_7.json"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def items(value):
    return value if isinstance(value, list) else []


def week_key(now: datetime) -> str:
    monday = now.date() - timedelta(days=now.weekday())
    return monday.isoformat()


def campaign_bonus(candidate: dict) -> tuple[float, list[str]]:
    text = " ".join(str(candidate.get(k) or "") for k in ("title", "news_title", "category", "format", "reason")).lower()
    terms = ("creatorpad", "creator pad", "creator task", "reward pool", "leaderboard", "campaign")
    if any(t in text for t in terms):
        return 18.0, ["possible_creatorpad_opportunity"]
    return 0.0, []


def market_action_bonus(candidate: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    context = candidate.get("derivatives_context") or {}
    if isinstance(context, dict):
        if abs(num(context.get("funding_rate"))) >= 0.0005:
            score += 5
            reasons.append("funding_extreme_context")
        if abs(num(context.get("oi_change_pct"))) >= 3:
            score += 5
            reasons.append("open_interest_change")
    if num(candidate.get("content_signal_score")) >= 70:
        score += 5
        reasons.append("strong_content_signal")
    return score, reasons


def recent_symbols() -> set[str]:
    if not LOG.exists():
        return set()
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-40:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("status") == "PUBLISHED_AUTONOMOUSLY":
            rows.append(row)
    return {str(r.get("symbol") or "").upper() for r in rows[-12:] if r.get("symbol")}


def verified_revenue() -> float:
    total = 0.0
    if not LOG.exists():
        return total
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        total += num(row.get("verified_revenue_usdt"))
        total += num(row.get("commission_usdt"))
    return total


def main() -> None:
    now = datetime.now(timezone.utc)
    ranking = load(RANKING)
    perf = load(PERF)
    growth = load(GROWTH)
    news = load(NEWS)
    candidates = items(ranking.get("candidates")) or items(ranking.get("ranked_stories"))
    recent = recent_symbols()
    revenue = verified_revenue()

    # The agent may choose strategy; it may not invent monetization evidence.
    monetization_mode = "verified_revenue" if revenue > 0 else "proxy_optimization"
    candidates_out = []
    for idx, raw in enumerate(candidates[:30]):
        if not isinstance(raw, dict):
            continue
        c = dict(raw)
        base = num(c.get("ranker_score") or c.get("score"))
        bonus, reasons = market_action_bonus(c)
        cb, cr = campaign_bonus(c)
        bonus += cb
        reasons += cr
        symbol = str(c.get("symbol") or "").upper()
        repetition_penalty = 8.0 if symbol and symbol in recent else 0.0
        freshness = 5.0 if c.get("news_published_at") else 0.0
        economic_score = base + bonus + freshness - repetition_penalty
        c["economic_score"] = round(economic_score, 2)
        c["economic_reasons"] = reasons
        candidates_out.append(c)

    candidates_out.sort(key=lambda x: num(x.get("economic_score")), reverse=True)
    chosen = candidates_out[0] if candidates_out else {}

    # Detect current CreatorPad/reward language without pretending we have a
    # complete campaign API. The actual campaign terms must still be verified.
    news_text = json.dumps(news, ensure_ascii=False).lower()
    campaign_signal = any(term in news_text for term in ("creatorpad", "creator pad", "reward pool", "leaderboard"))

    avg_quality = num(perf.get("average_quality_score") or perf.get("avg_quality_score"))
    growth_views = num(growth.get("views") or growth.get("total_views"))
    if monetization_mode == "verified_revenue":
        primary_goal = "increase_verified_creator_revenue while protecting quality"
    elif campaign_signal:
        primary_goal = "discover and execute verified high-value CreatorPad opportunities while growing reader action"
    else:
        primary_goal = "build qualified reader action and audience trust until verified monetization data becomes available"

    mission = {
        "version": "7.0",
        "generated_at": now.isoformat(),
        "week_start_utc": week_key(now),
        "mission": "SURVIVE -> MONETIZE -> GROW -> LEARN -> PROTECT_REPUTATION",
        "primary_goal": primary_goal,
        "monetization_mode": monetization_mode,
        "verified_revenue_usdt_observed": round(revenue, 8),
        "proxy_metrics_available": {
            "average_quality_score": avg_quality,
            "known_views": growth_views,
        },
        "decision": {
            "action": "PURSUE" if chosen else "WAIT",
            "selected_category": chosen.get("category"),
            "selected_symbol": chosen.get("symbol"),
            "selected_news": chosen.get("news_title"),
            "economic_score": chosen.get("economic_score"),
            "why": chosen.get("economic_reasons", []),
        },
        "hard_rules": [
            "Never call views, likes, comments or token clicks revenue.",
            "Never invent commission, campaign eligibility or reward amounts.",
            "CreatorPad requirements must be satisfied at first publication when a campaign is actually selected.",
            "Prefer original, relevant, high-quality work over volume farming.",
            "Never sacrifice factual accuracy or TradingView asset/story coherence for monetization.",
            "The agent can choose PUBLISH, WAIT, PIVOT, RESEARCH or FOLLOW_UP; it cannot bypass safety or platform rules.",
        ],
        "strategy": {
            "exploration_rate": 0.22,
            "repeat_symbol_penalty": 8,
            "campaign_signal_bonus": 18,
            "strong_content_signal_bonus": 5,
            "derivatives_context_bonus_cap": 10,
        },
        "top_opportunities": [
            {
                "category": c.get("category"),
                "symbol": c.get("symbol"),
                "title": c.get("news_title") or c.get("title"),
                "economic_score": c.get("economic_score"),
                "reasons": c.get("economic_reasons", []),
            }
            for c in candidates_out[:10]
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(mission, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(mission, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
