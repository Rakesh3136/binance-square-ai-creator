"""Creator 7.1 human-like adaptive publication cadence authority.

GitHub wakes hourly only to sense the market. Publication timing is NOT a fixed
3-hour quota: the creator decides when a human editor would reasonably post,
wait, or research based on opportunity strength, freshness, repetition and the
last verified publication time.
"""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
IDENTITY = ROOT / "data/live/creator_identity_6_6.json"
PREF = ROOT / "data/live/editorial_preflight.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
GROWTH = ROOT / "data/intelligence/creator_growth.json"
LOG = ROOT / "analytics/publication_log.jsonl"
MISSION = ROOT / "data/live/creator_mission_7.json"
GOAL = ROOT / "data/intelligence/creator_7_day_goal.json"
OUT = ROOT / "data/live/autonomous_cadence_6.json"


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
    for line in LOG.read_text(encoding="utf-8").splitlines()[-160:]:
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


def refresh_mission() -> dict:
    script = ROOT / "src/creator_mission_7.py"
    try:
        subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True, timeout=30)
    except Exception as exc:
        print(f"mission_refresh_failed={exc}")
    return load(MISSION)


def ensure_goal(now):
    goal = load(GOAL)
    expires = parse_dt(str(goal.get("expires_at") or ""))
    if not goal or not expires or expires <= now:
        goal = {
            "version": "7.1",
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
    mission = refresh_mission()
    ranking = load(RANKING)
    identity = load(IDENTITY)
    pref = load(PREF)
    feedback = load(FEEDBACK)
    growth = load(GROWTH)
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
    mission_decision = mission.get("decision") if isinstance(mission.get("decision"), dict) else {}
    mission_action = str(mission_decision.get("action") or "").upper()
    mission_score = num(mission_decision.get("selected_score"))
    effective_score = max(score, mission_score)

    reasons = []
    publish = False
    decision = "WAIT"
    action = "wait_for_stronger_or_fresher_opportunity"
    cooldown_minutes = 0

    # Human-like cadence: event-driven rather than quota-driven. A strong story
    # can publish quickly; an ordinary story waits; a weak story is skipped.
    if manual:
        publish = True
        decision = "PUBLISH"
        action = "publish_manual_request_after_quality_gates"
        reasons.append("manual_topic")
    elif not selected:
        reasons.append("no_selected_opportunity")
    elif mission_action == "WAIT":
        reasons.append("mission_wait")
    elif mission_action == "RESEARCH_MORE":
        decision = "RESEARCH"
        action = "research_until_quality_floor_is_met"
        reasons.append("mission_research_more")
    elif mission_action == "PIVOT":
        decision = "PIVOT"
        action = "choose_next_best_story_with_different_asset"
        reasons.append("mission_pivot")
    elif previous is None:
        publish = True
        decision = "PUBLISH"
        action = "publish_first_valid_high_information_post"
        reasons.append("first_publication")
    elif news_title and category in {"breaking_news", "news_market_impact"} and news_age_hours is not None and news_age_hours <= 3 and effective_score >= 72 and (minutes_since is None or minutes_since >= 45):
        publish = True
        decision = "PUBLISH"
        action = "publish_fresh_breaking_news"
        cooldown_minutes = 45
        reasons.append("fresh_breaking_news")
    elif mission_action == "ACT_NOW" and effective_score >= 105 and (minutes_since is None or minutes_since >= 60):
        publish = True
        decision = "PUBLISH"
        action = "mission_act_now"
        cooldown_minutes = 60
        reasons.append("mission_act_now")
    elif effective_score >= 125 and (minutes_since is None or minutes_since >= 75):
        publish = True
        decision = "PUBLISH"
        action = "publish_exceptional_opportunity"
        cooldown_minutes = 75
        reasons.append("exceptionally_strong_opportunity")
    elif effective_score >= 100 and (minutes_since is None or minutes_since >= 120):
        publish = True
        decision = "PUBLISH"
        action = "publish_high_value_opportunity"
        cooldown_minutes = 120
        reasons.append("high_value_opportunity")
    elif effective_score >= 82 and (minutes_since is None or minutes_since >= 180):
        publish = True
        decision = "PUBLISH"
        action = "publish_strong_opportunity"
        cooldown_minutes = 180
        reasons.append("strong_opportunity")
    elif effective_score >= 68 and (minutes_since is None or minutes_since >= 300):
        publish = True
        decision = "PUBLISH"
        action = "publish_normal_opportunity_after_longer_spacing"
        cooldown_minutes = 300
        reasons.append("normal_opportunity_after_spacing")
    else:
        reasons.append("wait_for_better_story_or_natural_spacing")

    if effective_score < 60 and not manual:
        publish = False
        decision = "RESEARCH"
        action = "research_market_until_quality_floor_is_met"
        reasons.append("quality_floor")

    if same_symbol_recent >= 3 and category not in {"breaking_news", "news_market_impact"} and not manual:
        publish = False
        decision = "PIVOT"
        action = "choose_next_best_story_with_different_asset"
        reasons.append("recent_asset_overexposure")

    result = {
        "version": "7.1-human-cadence",
        "generated_at": now.isoformat(),
        "publish": publish,
        "decision": decision,
        "strategic_action": action,
        "mission": mission,
        "seven_day_goal": goal,
        "minutes_since_last_publication": None if minutes_since is None else round(minutes_since, 1),
        "selected_category": category,
        "selected_symbol": symbol or None,
        "selected_news": news_title or None,
        "ranker_score": score,
        "mission_score": mission_score,
        "effective_score": effective_score,
        "news_age_hours": None if news_age_hours is None else round(news_age_hours, 2),
        "manual_topic": manual,
        "same_symbol_in_last_five": same_symbol_recent,
        "learning_signals": {
            "quality_score": num(feedback.get("overall_quality") or feedback.get("quality_score") or feedback.get("score")),
            "growth_score": num(growth.get("growth_score") or growth.get("score")),
        },
        "reasons": reasons,
        "policy": {
            "scheduler_wake_interval": "hourly_sensing_only",
            "fixed_three_hour_quota": False,
            "publication_interval": "event_and_quality_driven",
            "human_like_cadence": True,
            "breaking_news_minimum_spacing_minutes": 45,
            "exceptional_minimum_spacing_minutes": 75,
            "high_value_minimum_spacing_minutes": 120,
            "strong_minimum_spacing_minutes": 180,
            "normal_minimum_spacing_minutes": 300,
            "minimum_quality_score": 60,
            "accuracy_over_frequency": True,
            "revenue_claims_require_verified_account_evidence": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"publish={'true' if publish else 'false'}")


if __name__ == "__main__":
    main()
