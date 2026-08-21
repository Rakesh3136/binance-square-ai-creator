import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARKET = Path("data/live/market_snapshot.json")
NEWS = Path("data/live/news_snapshot.json")
MEMORY = Path("analytics/strategy_memory.json")
PUBLICATIONS = Path("analytics/publication_log.jsonl")
OUTPUT = Path("data/live/editorial_preflight.json")

MIN_MARKET_SCORE = 72.0
MIN_EXCEPTIONAL_SCORE = 90.0
MAX_RECENT_SAME_TOPIC = 2
NEWS_FRESH_MINUTES = 35
MEMORY_REPEAT_PENALTY = 18.0
MEMORY_HARD_BLOCK_COUNT = 3


def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def recent_topics(known_symbols):
    counts = Counter()
    if not PUBLICATIONS.exists():
        return counts
    cutoff = datetime.now(timezone.utc) - timedelta(hours=18)
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            dt = datetime.fromisoformat(str(row.get("published_at", "")).replace("Z", "+00:00"))
            if dt < cutoff:
                continue
            raw = str(row.get("symbol") or row.get("topic") or "").upper()
            if not raw:
                continue
            matched = None
            for symbol in known_symbols:
                base = symbol[:-4] if symbol.endswith("USDT") else symbol
                if re.search(rf"(?<![A-Z0-9])\$?{re.escape(base)}(?![A-Z0-9])", raw):
                    matched = symbol
                    break
            counts[matched or raw] += 1
        except Exception:
            continue
    return counts


def memory_topics(memory):
    counts = Counter()
    for row in memory.get("recent_performance_observations") or []:
        topic = str(row.get("topic") or "").upper().strip()
        if topic:
            counts[topic] += 1
    return counts


def main():
    market = load(MARKET)
    news = load(NEWS)
    memory = load(MEMORY)

    market_items = market.get("top_content_signals") or []
    known_symbols = {str(item.get("symbol") or "").upper() for item in market_items if item.get("symbol")}
    publication_counts = recent_topics(known_symbols)
    memory_counts = memory_topics(memory)

    candidates = []
    for item in market_items:
        symbol = str(item.get("symbol") or "").upper()
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        score = float(item.get("content_signal_score") or 0)
        publication_penalty = min(40.0, publication_counts.get(symbol, 0) * 20.0)
        memory_penalty = min(54.0, memory_counts.get(base, 0) * MEMORY_REPEAT_PENALTY)
        adjusted = score - publication_penalty - memory_penalty
        exceptional = score >= MIN_EXCEPTIONAL_SCORE
        repeated = publication_counts.get(symbol, 0) >= MAX_RECENT_SAME_TOPIC or memory_counts.get(base, 0) >= MEMORY_HARD_BLOCK_COUNT
        candidates.append({
            "type": "market",
            "topic": symbol,
            "raw_score": round(score, 2),
            "adjusted_score": round(adjusted, 2),
            "recent_count": publication_counts.get(symbol, 0),
            "memory_count": memory_counts.get(base, 0),
            "exceptional": exceptional,
            "repeated": repeated,
        })

    now = datetime.now(timezone.utc)
    fresh_news = 0
    for article in news.get("articles") or []:
        try:
            dt = datetime.fromisoformat(str(article.get("published_at", "")).replace("Z", "+00:00"))
            if now - dt <= timedelta(minutes=NEWS_FRESH_MINUTES):
                fresh_news += 1
        except Exception:
            continue

    # Major verified breaking news may override a repetition penalty.
    news_override = fresh_news > 0
    eligible = [c for c in candidates if not c["repeated"] or news_override]
    best = max(eligible, key=lambda x: x["adjusted_score"], default=None)
    market_ok = bool(best and best["adjusted_score"] >= MIN_MARKET_SCORE)
    news_ok = fresh_news > 0
    run_ai = market_ok or news_ok
    if news_ok and not market_ok:
        reason = "fresh_news"
    elif market_ok:
        reason = "strong_market_opportunity"
    else:
        reason = "no_strong_opportunity"

    result = {
        "generated_at": now.isoformat(),
        "run_ai": run_ai,
        "reason": reason,
        "best_market_candidate": best,
        "fresh_news_count": fresh_news,
        "recent_topic_counts": dict(publication_counts),
        "memory_topic_counts": dict(memory_counts),
        "strategy_memory_loaded": bool(memory),
        "rules": {
            "min_market_score": MIN_MARKET_SCORE,
            "recent_same_topic_limit": MAX_RECENT_SAME_TOPIC,
            "exceptional_override_score": MIN_EXCEPTIONAL_SCORE,
            "memory_repeat_penalty": MEMORY_REPEAT_PENALTY,
            "memory_hard_block_count": MEMORY_HARD_BLOCK_COUNT,
            "breaking_news_override": news_override,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
