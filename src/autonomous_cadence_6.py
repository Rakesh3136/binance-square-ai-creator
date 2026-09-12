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


def run_guard(script_name: str) -> dict:
    script = ROOT / "src" / script_name
    try:
        proc = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.returncode == 0:
            if script_name == "signal_first_router.py":
                return load(ROOT / "data/live/signal_first_routing.json")
            if script_name == "content_portfolio_guard.py":
                return load(ROOT / "data/live/content_portfolio_guard.json")
        print(f"{script_name}_failed; preserving prior cadence decision")
    except Exception as exc:
        print(f"{script_name}_unavailable={exc}")
    return {}


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
        reasons.append("fresh_breaking_news")
    elif mission_action == "ACT_NOW" and effective_score >= 110 and (minutes_since is None or minutes_since >= 15):
        publish = True
        decision = "PUBLISH"
        action = "mission_act_now_short_spacing_override"
        reasons.append("mission_act_now_exception")
    elif mission_action == "ACT_NOW" and effective_score >= 105 and (minutes_since is None or minutes_since >= 30):
        publish = True
        decision = "PUBLISH"
        action = "mission_act_now_reduced_spacing"
        reasons.append("mission_act_now_reduced_spacing")
    elif effective_score >= 125 and (minutes_since is None or minutes_since >= 75):
        publish = True
        decision = "PUBLISH"
        action = "publish_exceptional_opportunity"
        reasons.append("exceptionally_strong_opportunity")
    elif effective_score >= 100 and (minutes_since is None or minutes_since >= 120):
        publish = True
        decision = "PUBLISH"
        action = "publish_high_value_opportunity"
        reasons.append("high_value_opportunity")
    elif effective_score >= 82 and (minutes_since is None or minutes_since >= 180):
        publish = True
        decision = "PUBLISH"
        action = "publish_strong_opportunity"
        reasons.append("strong_opportunity")
    elif effective_score >= 68 and (minutes_since is None or minutes_since >= 300):
        publish = True
        decision = "PUBLISH"
        action = "publish_normal_opportunity_after_longer_spacing"
        reasons.append("normal_opportunity_after_spacing")
    else:
        reasons.append("wait_for_better_story_or_natural_spacing")

    if effective_score < 60 and not manual:
        publish = False
        decision = "RESEARCH"
        action = "research_market_until_quality_floor_is_met"
        reasons.append("quality_floor")

    result = {
        "version": "7.2-human-cadence-signal-first-portfolio",
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
            "accuracy_over_frequency": True,
            "no_repetitive_posting": True,
            "generic_news_cannot_create_btc_fallback": True,
            "wait_for_different_story_when_portfolio_is_repetitive": True,
            "qualified_signal_beats_meme": True,
            "revenue_claims_require_verified_account_evidence": True,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Signal-first routing selects the primary market thesis. The content
    # portfolio manager then prevents one asset/story from consuming the feed.
    if publish:
        route = run_guard("signal_first_router.py")
        result["signal_first_routing"] = route
        if route and route.get("publish") is False:
            publish = False
            result["publish"] = False
            result["decision"] = route.get("decision", "WAIT")
            result["strategic_action"] = "signal_first_wait_or_research"
            result["reasons"] = reasons + [route.get("reason", "signal_first_router")]

    if publish:
        portfolio = run_guard("content_portfolio_guard.py")
        result["content_portfolio_guard"] = portfolio
        if portfolio and portfolio.get("publish") is False:
            publish = False
            result["publish"] = False
            result["decision"] = portfolio.get("decision", "WAIT_FOR_DIFFERENT_STORY")
            result["strategic_action"] = "wait_or_research_for_non_repetitive_story"
            result["reasons"] = reasons + [portfolio.get("reason", "content_portfolio_guard")]
        elif portfolio.get("selected"):
            selected_after_guard = portfolio.get("selected")
            result["selected_category"] = str(selected_after_guard.get("category") or selected_after_guard.get("lane") or "").lower()
            result["selected_symbol"] = str(selected_after_guard.get("symbol") or "").upper()
            result["reasons"] = reasons + ["content_portfolio_diversity_pass"]

    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"publish={'true' if result.get('publish') else 'false'}")


if __name__ == "__main__":
    main()
