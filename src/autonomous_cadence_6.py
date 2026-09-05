"""Creator 7.0 autonomous mission + adaptive cadence authority.

The workflow wakes hourly, but this authority decides whether to publish, wait,
pivot or research. It consumes the persistent Creator 7.0 mission decision and
never invents account-level revenue.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
IDENTITY = ROOT / "data/live/creator_identity_6_6.json"
PREF = ROOT / "data/live/editorial_preflight.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
GROWTH = ROOT / "data/intelligence/creator_growth.json"
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/autonomous_cadence_6.json"
MISSION = ROOT / "data/live/creator_mission_7.json"
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


def parse_dt(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def recent_publications():
    if not LOG.exists():
        return []
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-120:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("status") == "PUBLISHED_AUTONOMOUSLY":
            rows.append(row)
    return rows[-20:]


def last_publication():
    latest = None
    for row in recent_publications():
        dt = parse_dt(str(row.get("published_at") or row.get("recorded_at") or ""))
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest


def ensure_goal(now):
    goal = load(GOAL)
    expires = parse_dt(str(goal.get("expires_at") or ""))
    if not goal or not expires or expires <= now:
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
    GOAL.parent.mkdir(parents=True, exist_ok=True)
    GOAL.write_text(json.dumps(goal, indent=2, ensure_ascii=False), encoding="utf-8")
    return goal


def main() -> None:
    now = datetime.now(timezone.utc)
    ranking = load(RANKING)
    identity = load(IDENTITY)
    pref = load(PREF)
    feedback = load(FEEDBACK)
    growth = load(GROWTH)
    mission = load(MISSION)
    selected = ranking.get("selected") or pref.get("selected_opportunity") or identity.get("selected") or {}
    if not isinstance(selected, dict):
        selected = {}

    goal = ensure_goal(now)
    previous = last_publication()
    minutes_since = None if previous is None else max(0.0, (now - previous).total_seconds() / 60.0)
    score = num(selected.get("ranker_score") or selected.get("identity_score") or selected.get("score"))
    category = str(selected.get("category") or selected.get("lane") or "").lower()
    symbol = str(selected.get("symbol") or "").upper()
    news_title = str(selected.get("news_title") or selected.get("title") or "").strip()
    published_news_at = parse_dt(str(selected.get("news_published_at") or selected.get("published_at") or ""))
    news_age_hours = None if not published_news_at else max(0.0, (now - published_news_at).total_seconds() / 3600.0)
    manual = bool(pref.get("manual_topic")) or bool(selected.get("manual_topic"))

    recent = recent_publications()
    same_symbol_recent = sum(1 for r in recent[-5:] if symbol and str(r.get("symbol") or "").upper() == symbol)
    learned = feedback.get("learned_preferences") or {}
    growth_score = num(growth.get("growth_score") or growth.get("score"))
    mission_decision = mission.get("decision") if isinstance(mission.get("decision"), dict) else {}
    mission_action = str(mission_decision.get("action") or "").upper()

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

    monetization = {
        "program": "Binance Square Write to Earn",
        "verified_revenue_available": False,
        "known_base_commission_percent": 20,
        "known_top_1_30_total_percent": 50,
        "known_top_31_100_total_percent": 30,
        "optimization_target": "qualified reader actions, not raw views alone",
        "revenue_claim_policy": "never claim earnings without verified account-level evidence",
    }

    reasons = []
    publish = False
    decision = "WAIT"
    action = "wait_for_stronger_or_fresher_opportunity"

    if manual:
        publish = True
        decision = "PUBLISH"
        action = "publish_manual_request_after_quality_gates"
        reasons.append("manual_topic")
    elif not selected:
        reasons.append("no_selected_opportunity")
    elif mission_action == "WAIT":
        decision = "WAIT"
        action = "mission_wait"
        reasons.append("mission_wait")
    elif mission_action == "RESEARCH_MORE":
        decision = "RESEARCH"
        action = "research_until_mission_quality_floor_is_met"
        reasons.append("mission_research_more")
    elif mission_action == "PIVOT" and same_symbol_recent >= 3:
        decision = "PIVOT"
        action = "choose_next_best_story_with_different_asset"
        reasons.append("mission_pivot")
    elif previous is None:
        publish = True
        decision = "PUBLISH"
        action = "publish_first_valid_high_information_post"
        reasons.append("first_publication")
    elif news_title and category in {"breaking_news", "news_market_impact"} and news_age_hours is not None and news_age_hours <= 6 and score >= 65:
        publish = True
        decision = "PUBLISH"
        action = "publish_fresh_breaking_news"
        reasons.append("fresh_breaking_news")
    elif mission_action == "ACT_NOW" and score >= 95 and (minutes_since is None or minutes_since >= 45):
        publish = True
        decision = "PUBLISH"
        action = "mission_act_now"
        reasons.append("mission_act_now")
    elif score >= 110 and minutes_since is not None and minutes_since >= 60:
        publish = True
        decision = "PUBLISH"
        action = "publish_exceptional_opportunity"
        reasons.append("exceptionally_strong_opportunity")
    elif minutes_since is not None and minutes_since >= 90 and score >= 78:
        publish = True
        decision = "PUBLISH"
        action = "publish_strong_opportunity_after_cooldown"
        reasons.append("strong_opportunity_after_cooldown")
    elif minutes_since is not None and minutes_since >= 180 and score >= 65:
        publish = True
        decision = "PUBLISH"
        action = "publish_after_maximum_cooldown"
        reasons.append("maximum_cadence_interval")
    else:
        reasons.append("wait_for_stronger_or_fresher_opportunity")

    if score < 60 and not manual:
        publish = False
        decision = "WAIT"
        action = "research_market_until_quality_floor_is_met"
        reasons.append("quality_floor")

    if same_symbol_recent >= 3 and category not in {"breaking_news", "news_market_impact"} and not manual:
        publish = False
        decision = "PIVOT"
        action = "choose_next_best_story_with_different_asset"
        reasons.append("recent_asset_overexposure")

    mission_output = {
        "version": "7.0",
        "decision": decision,
        "action": action,
        "primary_goal": goal["primary_goal"],
        "goal_expires_at": goal["expires_at"],
        "mission_input_action": mission_action or None,
        "evidence": evidence,
        "monetization": monetization,
        "learned_preferences": learned,
        "rules": [
            "optimize for qualified reader actions rather than vanity metrics",
            "prefer evidence-backed high-intent stories",
            "use fresh assets when opportunity quality is comparable",
            "follow up on proven winners only when new evidence exists",
            "abandon weak stories instead of forcing publication",
            "actual revenue remains unknown until verified",
        ],
    }

    result = {
        "version": "7.0",
        "generated_at": now.isoformat(),
        "publish": publish,
        "decision": decision,
        "strategic_action": action,
        "mission": mission_output,
        "minutes_since_last_publication": None if minutes_since is None else round(minutes_since, 1),
        "selected_category": category,
        "selected_symbol": symbol or None,
        "selected_news": news_title or None,
        "ranker_score": score,
        "news_age_hours": None if news_age_hours is None else round(news_age_hours, 2),
        "manual_topic": manual,
        "same_symbol_in_last_five": same_symbol_recent,
        "reasons": reasons,
        "policy": {
            "wake_interval": "hourly",
            "publication_interval": "adaptive",
            "mission_authority": True,
            "fresh_breaking_news_override_hours": 6,
            "strong_opportunity_threshold": 78,
            "exceptional_opportunity_threshold": 110,
            "minimum_quality_score": 60,
            "normal_cooldown_minutes": 90,
            "maximum_cooldown_minutes": 180,
            "accuracy_over_frequency": True,
            "mission_horizon_days": 7,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    MISSION.write_text(json.dumps(mission_output, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"publish={'true' if publish else 'false'}")


if __name__ == "__main__":
    main()
