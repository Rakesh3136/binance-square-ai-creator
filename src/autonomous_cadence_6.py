"""Creator 6.6 adaptive cadence gate.

GitHub Actions wakes the creator hourly so market intelligence stays fresh, but
publication is decided from evidence rather than a fixed three-hour timer.
The gate protects against spam while allowing strong fresh opportunities and
material breaking news to publish sooner.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
IDENTITY = ROOT / "data/live/creator_identity_6_6.json"
PREF = ROOT / "data/live/editorial_preflight.json"
LOG = ROOT / "analytics/publication_log.jsonl"
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


def last_publication():
    if not LOG.exists():
        return None
    latest = None
    for line in LOG.read_text(encoding="utf-8").splitlines()[-160:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict) or row.get("status") != "PUBLISHED_AUTONOMOUSLY":
            continue
        dt = parse_dt(str(row.get("published_at") or row.get("recorded_at") or ""))
        if dt and (latest is None or dt > latest):
            latest = dt
    return latest


def main() -> None:
    now = datetime.now(timezone.utc)
    ranking = load(RANKING)
    identity = load(IDENTITY)
    pref = load(PREF)
    selected = ranking.get("selected") or pref.get("selected_opportunity") or identity.get("selected") or {}
    if not isinstance(selected, dict):
        selected = {}

    manual = bool(pref.get("manual_topic")) or bool(selected.get("manual_topic"))
    score = num(selected.get("ranker_score") or selected.get("identity_score") or selected.get("score"))
    category = str(selected.get("category") or selected.get("lane") or "").lower()
    news_title = str(selected.get("news_title") or selected.get("title") or "").strip()
    published_news_at = parse_dt(str(selected.get("news_published_at") or selected.get("published_at") or ""))
    news_age_hours = None if not published_news_at else max(0.0, (now - published_news_at).total_seconds() / 3600.0)

    previous = last_publication()
    minutes_since = None if previous is None else max(0.0, (now - previous).total_seconds() / 60.0)

    # Automatic cadence policy: hourly intelligence, variable publication cadence.
    reasons = []
    publish = False
    if manual:
        publish = True
        reasons.append("manual_topic")
    elif not selected:
        reasons.append("no_selected_opportunity")
    elif previous is None:
        publish = True
        reasons.append("first_publication")
    elif news_title and category in {"breaking_news", "news_market_impact"} and news_age_hours is not None and news_age_hours <= 6 and score >= 65:
        publish = True
        reasons.append("fresh_breaking_news")
    elif score >= 110 and (minutes_since is None or minutes_since >= 60):
        publish = True
        reasons.append("exceptionally_strong_opportunity")
    elif minutes_since is not None and minutes_since >= 90 and score >= 78:
        publish = True
        reasons.append("strong_opportunity_after_cooldown")
    elif minutes_since is not None and minutes_since >= 180 and score >= 65:
        publish = True
        reasons.append("maximum_cadence_interval")
    else:
        reasons.append("wait_for_stronger_or_fresher_opportunity")

    if score < 60 and not manual:
        publish = False
        reasons.append("quality_floor")

    result = {
        "version": "6.6",
        "generated_at": now.isoformat(),
        "publish": publish,
        "decision": "PUBLISH" if publish else "WAIT",
        "minutes_since_last_publication": None if minutes_since is None else round(minutes_since, 1),
        "selected_category": category,
        "selected_symbol": selected.get("symbol"),
        "selected_news": news_title or None,
        "ranker_score": score,
        "news_age_hours": None if news_age_hours is None else round(news_age_hours, 2),
        "manual_topic": manual,
        "reasons": reasons,
        "policy": {
            "wake_interval": "hourly",
            "publication_interval": "adaptive",
            "fresh_breaking_news_override_hours": 6,
            "strong_opportunity_threshold": 78,
            "exceptional_opportunity_threshold": 110,
            "minimum_quality_score": 60,
            "normal_cooldown_minutes": 90,
            "maximum_cooldown_minutes": 180,
            "accuracy_over_frequency": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"publish={'true' if publish else 'false'}" )


if __name__ == "__main__":
    main()
