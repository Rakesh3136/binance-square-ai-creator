import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARKET = Path("data/live/market_snapshot.json")
NEWS = Path("data/live/news_snapshot.json")
MEMORY = Path("analytics/strategy_memory.json")
PUBLICATIONS = Path("analytics/publication_log.jsonl")
OUTPUT = Path("data/live/editorial_preflight.json")

# Free-tier protection: the monitor can run frequently, but Gemini should only
# be spent on genuinely promising opportunities.
MIN_MARKET_SCORE = 72.0
MIN_EXCEPTIONAL_SCORE = 90.0
MAX_RECENT_SAME_TOPIC = 2
NEWS_FRESH_MINUTES = 35


def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def recent_topics():
    if not PUBLICATIONS.exists():
        return Counter()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=18)
    counts = Counter()
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            dt = datetime.fromisoformat(str(row.get("published_at", "")).replace("Z", "+00:00"))
            if dt >= cutoff:
                topic = str(row.get("topic") or row.get("symbol") or "").upper()
                if topic:
                    counts[topic] += 1
        except Exception:
            continue
    return counts


def main():
    market = load(MARKET)
    news = load(NEWS)
    memory = load(MEMORY)
    counts = recent_topics()

    candidates = []
    for item in market.get("top_content_signals") or []:
        symbol = str(item.get("symbol") or "").upper()
        score = float(item.get("content_signal_score") or 0)
        penalty = min(25.0, counts.get(symbol, 0) * 14.0)
        adjusted = score - penalty
        exceptional = score >= MIN_EXCEPTIONAL_SCORE
        if counts.get(symbol, 0) >= MAX_RECENT_SAME_TOPIC and not exceptional:
            adjusted -= 20.0
        candidates.append({
            "type": "market",
            "topic": symbol,
            "raw_score": round(score, 2),
            "adjusted_score": round(adjusted, 2),
            "recent_count": counts.get(symbol, 0),
            "exceptional": exceptional,
        })

    now = datetime.now(timezone.utc)
    fresh_news = 0
    for article in news.get("articles") or []:
        value = article.get("published_at")
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if now - dt <= timedelta(minutes=NEWS_FRESH_MINUTES):
                fresh_news += 1
        except Exception:
            continue

    best = max(candidates, key=lambda x: x["adjusted_score"], default=None)
    market_ok = bool(best and (best["adjusted_score"] >= MIN_MARKET_SCORE or best["exceptional"]))
    news_ok = fresh_news > 0

    # A fresh news lead can justify one Gemini research call, but repeated
    # market-only noise cannot. Strategy memory is advisory, never proof.
    run_ai = market_ok or news_ok
    reason = "fresh_news" if news_ok and not market_ok else ("strong_market_opportunity" if market_ok else "no_strong_opportunity")

    result = {
        "generated_at": now.isoformat(),
        "run_ai": run_ai,
        "reason": reason,
        "best_market_candidate": best,
        "fresh_news_count": fresh_news,
        "recent_topic_counts": dict(counts),
        "strategy_memory_loaded": bool(memory),
        "rules": {
            "min_market_score": MIN_MARKET_SCORE,
            "recent_same_topic_limit": MAX_RECENT_SAME_TOPIC,
            "exceptional_override_score": MIN_EXCEPTIONAL_SCORE,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
