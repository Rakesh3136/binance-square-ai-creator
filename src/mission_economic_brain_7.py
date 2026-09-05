"""Creator 7.0 mission + economic decision engine.

Turns market intelligence, opportunity ranking, cadence, growth learning and
Binance Square monetization mechanics into an explicit strategic decision.
This engine does NOT invent revenue: actual Write-to-Earn revenue remains
unknown unless verified account-level data is supplied.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREF = ROOT / "data/live/editorial_preflight.json"
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
CADENCE = ROOT / "data/live/autonomous_cadence_6.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
GROWTH = ROOT / "data/intelligence/creator_growth.json"
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/mission_economic_brain_7.json"
GOAL = ROOT / "data/intelligence/creator_7_day_goal.json"


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


def recent_posts() -> list[dict]:
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-100:]:
        try:
            row = json.loads(line)
            if isinstance(row, dict) and row.get("status") == "PUBLISHED_AUTONOMOUSLY":
                rows.append(row)
        except Exception:
            pass
    return rows[-20:]


def main() -> None:
    now = datetime.now(timezone.utc)
    pref = load(PREF)
    ranking = load(RANKING)
    cadence = load(CADENCE)
    feedback = load(FEEDBACK)
    growth = load(GROWTH)
    selected = ranking.get("selected") or pref.get("selected_opportunity") or {}
    if not isinstance(selected, dict):
        selected = {}

    goal = load(GOAL)
    if not goal or goal.get("expires_at") and str(goal.get("expires_at")) <= now.isoformat():
        goal = {
            "version": "7.0",
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "primary_goal": "maximize legitimate Binance Square monetization opportunity",
            "secondary_goals": [
                "increase qualified reader actions",
                "increase trusted audience growth",
                "learn which stories and formats produce durable performance",
            ],
            "hard_rules": [
                "never invent revenue or reader trades",
                "never manipulate readers into trading",
                "never sacrifice factual accuracy for monetization",
                "never publish merely to satisfy a quota",
            ],
            "experiments": [],
        }

    score = num(selected.get("ranker_score") or selected.get("score"))
    category = str(selected.get("category") or selected.get("lane") or "").lower()
    symbol = str(selected.get("symbol") or "").upper()
    news = str(selected.get("news_title") or selected.get("title") or "").strip()
    recent = recent_posts()
    same_symbol_recent = sum(1 for r in recent[-5:] if str(r.get("symbol") or "").upper() == symbol and symbol)

    # Monetization mechanics are known; actual earnings are not.
    monetization = {
        "program": "Binance Square Write to Earn",
        "verified_revenue_available": False,
        "known_base_commission_percent": 20,
        "known_top_1_30_total_percent": 50,
        "known_top_31_100_total_percent": 30,
        "commission_trigger": "eligible reader clicks coin cashtag/trading widget and completes a qualifying trade",
        "optimization_target": "qualified reader action, not raw views alone",
        "revenue_claim_policy": "never claim earnings unless account-level evidence verifies them",
    }

    feedback_pref = feedback.get("learned_preferences") or {}
    growth_score = num(growth.get("growth_score") or growth.get("score"))
    evidence = []
    if score >= 110:
        evidence.append("exceptional_opportunity")
    elif score >= 78:
        evidence.append("strong_opportunity")
    if category in {"breaking_news", "news_market_impact", "technical_breakout", "volume_anomaly", "liquidation", "new_listing"}:
        evidence.append("high_intent_story_type")
    if symbol and same_symbol_recent == 0:
        evidence.append("asset_freshness")
    if growth_score > 0:
        evidence.append("growth_signal_available")

    # Strategic choice: publish only when the opportunity is strong enough.
    if bool(cadence.get("publish")) and score >= 78:
        decision = "PUBLISH"
        action = "publish_highest_expected_value_story"
    elif score >= 60:
        decision = "WAIT_AND_RESEARCH"
        action = "continue_intelligence_until_opportunity_improves"
    else:
        decision = "WAIT"
        action = "do_not_publish_low_value_content"

    if same_symbol_recent >= 3 and category not in {"breaking_news", "news_market_impact"}:
        decision = "PIVOT"
        action = "choose_next_best_story_with_different_asset"
        evidence.append("recent_asset_overexposure")

    mission = {
        "version": "7.0",
        "generated_at": now.isoformat(),
        "decision": decision,
        "action": action,
        "goal_window": {"started_at": goal.get("started_at"), "expires_at": goal.get("expires_at")},
        "primary_goal": goal.get("primary_goal"),
        "selected_opportunity": {
            "category": category,
            "symbol": symbol or None,
            "news_title": news or None,
            "ranker_score": score,
        },
        "evidence": evidence,
        "monetization": monetization,
        "learned_preferences": feedback_pref,
        "strategic_rules": [
            "optimize for qualified reader actions rather than vanity metrics",
            "prefer high-intent evidence-backed stories",
            "use fresh assets when opportunity quality is comparable",
            "follow up on proven winners when new evidence exists",
            "abandon weak stories instead of forcing publication",
            "treat actual revenue as unknown until verified",
        ],
    }
    GOAL.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    GOAL.write_text(json.dumps(goal, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(mission, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(mission, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
