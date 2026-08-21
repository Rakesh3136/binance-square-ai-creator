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
NEWS_FRESH_MINUTES = 35
MEMORY_REPEAT_PENALTY = 18.0
MEMORY_HARD_BLOCK_COUNT = 3
CATEGORY_REPEAT_PENALTY = 14.0


def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def recent_publications(known_symbols):
    rows = []
    if not PUBLICATIONS.exists():
        return rows
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            dt = datetime.fromisoformat(str(row.get("published_at", "")).replace("Z", "+00:00"))
            if dt < cutoff:
                continue
            raw = str(row.get("symbol") or row.get("topic") or "").upper()
            matched = None
            for symbol in known_symbols:
                base = symbol[:-4] if symbol.endswith("USDT") else symbol
                if re.search(rf"(?<![A-Z0-9])\$?{re.escape(base)}(?![A-Z0-9])", raw):
                    matched = symbol
                    break
            rows.append({**row, "_matched_symbol": matched or raw})
        except Exception:
            continue
    return rows


def memory_topics(memory):
    counts = Counter()
    for row in memory.get("recent_performance_observations") or []:
        topic = str(row.get("topic") or "").upper().strip()
        if topic:
            counts[topic] += 1
    return counts


def add_market_candidate(pool, category, item, score_boost=0.0):
    if not item:
        return
    symbol = str(item.get("symbol") or "").upper()
    if not symbol:
        return
    raw_score = float(item.get("content_signal_score") or 0)
    if category == "top_gainers":
        raw_score = min(100.0, abs(float(item.get("price_change_percent") or 0)) * 4.5 + float(item.get("intraday_range_percent") or 0))
    elif category == "top_losers":
        raw_score = min(100.0, abs(float(item.get("price_change_percent") or 0)) * 4.5 + float(item.get("intraday_range_percent") or 0))
    elif category == "volume_leaders":
        raw_score = min(100.0, float(item.get("content_signal_score") or 0) + 10.0)
    elif category == "new_listings":
        age_bonus = max(0.0, 25.0 - float(item.get("days_since_listing") or 30) * 3.0)
        raw_score = min(100.0, float(item.get("content_signal_score") or 0) + age_bonus)
    raw_score = min(100.0, raw_score + score_boost)
    pool.append({
        "type": "market",
        "category": category,
        "topic": symbol,
        "raw_score": round(raw_score, 2),
        "reason": {
            "top_gainers": "largest positive movers",
            "top_losers": "largest negative movers",
            "volume_leaders": "unusually large spot volume",
            "new_listings": "recently onboarded Binance spot asset",
            "high_volatility": "large intraday range",
            "BTC_ETH_market_context": "major-market context",
        }.get(category, category),
    })


def main():
    market = load(MARKET)
    news = load(NEWS)
    memory = load(MEMORY)

    market_items = market.get("top_content_signals") or []
    known_symbols = {str(item.get("symbol") or "").upper() for item in market_items if item.get("symbol")}
    publications = recent_publications(known_symbols)
    publication_counts = Counter(str(r.get("_matched_symbol") or "").upper() for r in publications)
    category_counts = Counter(str(r.get("content_category") or "").lower() for r in publications if r.get("content_category"))
    memory_counts = memory_topics(memory)

    pool = []
    for item in (market.get("top_gainers") or [])[:6]:
        add_market_candidate(pool, "top_gainers", item)
    for item in (market.get("top_losers") or [])[:6]:
        add_market_candidate(pool, "top_losers", item)
    for item in (market.get("highest_volume") or [])[:6]:
        add_market_candidate(pool, "volume_leaders", item)
    for item in (market.get("new_listing_market") or [])[:6]:
        add_market_candidate(pool, "new_listings", item, score_boost=5.0)

    # Include high-volatility names that may not be top gainers/losers.
    for item in sorted(market_items, key=lambda x: float(x.get("intraday_range_percent") or 0), reverse=True)[:5]:
        add_market_candidate(pool, "high_volatility", item, score_boost=3.0)

    # Explicit major-asset context is a separate editorial lane.
    majors = [x for x in market_items if str(x.get("symbol") or "") in {"BTCUSDT", "ETHUSDT"}]
    for item in majors:
        add_market_candidate(pool, "BTC_ETH_market_context", item, score_boost=4.0)

    unique = {}
    for candidate in pool:
        key = (candidate["category"], candidate["topic"])
        unique[key] = candidate
    pool = list(unique.values())

    for candidate in pool:
        symbol = candidate["topic"]
        base = symbol[:-4] if symbol.endswith("USDT") else symbol
        pub_penalty = min(50.0, publication_counts.get(symbol, 0) * 20.0)
        mem_penalty = min(54.0, memory_counts.get(base, 0) * MEMORY_REPEAT_PENALTY)
        cat_penalty = min(28.0, category_counts.get(candidate["category"], 0) * CATEGORY_REPEAT_PENALTY)
        candidate["recent_count"] = publication_counts.get(symbol, 0)
        candidate["memory_count"] = memory_counts.get(base, 0)
        candidate["category_recent_count"] = category_counts.get(candidate["category"], 0)
        candidate["adjusted_score"] = round(candidate["raw_score"] - pub_penalty - mem_penalty - cat_penalty, 2)
        candidate["repeated"] = candidate["recent_count"] >= 2 or candidate["memory_count"] >= MEMORY_HARD_BLOCK_COUNT

    fresh_news = 0
    for article in news.get("articles") or []:
        try:
            dt = datetime.fromisoformat(str(article.get("published_at", "")).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - dt <= timedelta(minutes=NEWS_FRESH_MINUTES):
                fresh_news += 1
        except Exception:
            continue

    # Do not let a single asset dominate the editorial calendar. Breaking news
    # is the only automatic override for a hard repetition block.
    news_override = fresh_news > 0
    eligible = [c for c in pool if (not c["repeated"] or news_override)]
    best = max(eligible, key=lambda x: x["adjusted_score"], default=None)
    market_ok = bool(best and best["adjusted_score"] >= MIN_MARKET_SCORE)
    run_ai = market_ok or fresh_news > 0
    reason = "fresh_news" if fresh_news > 0 and not market_ok else ("strong_market_opportunity" if market_ok else "no_strong_opportunity")

    if best:
        selected_opportunity = {
            "category": best["category"],
            "symbol": best["topic"],
            "reason": best["reason"],
            "instruction": (
                f"Prioritize the {best['category'].replace('_', ' ')} angle. Use {best['topic']} only if the supplied evidence makes it the strongest example. "
                "You may choose a different asset inside the same category if it creates a materially stronger evidence-based story."
            ),
        }
    else:
        selected_opportunity = None

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_ai": run_ai,
        "reason": reason,
        "selected_opportunity": selected_opportunity,
        "candidate_pool": sorted(pool, key=lambda x: x["adjusted_score"], reverse=True)[:18],
        "best_market_candidate": best,
        "fresh_news_count": fresh_news,
        "recent_topic_counts": dict(publication_counts),
        "recent_category_counts": dict(category_counts),
        "memory_topic_counts": dict(memory_counts),
        "strategy_memory_loaded": bool(memory),
        "rules": {
            "min_market_score": MIN_MARKET_SCORE,
            "memory_repeat_penalty": MEMORY_REPEAT_PENALTY,
            "memory_hard_block_count": MEMORY_HARD_BLOCK_COUNT,
            "category_repeat_penalty": CATEGORY_REPEAT_PENALTY,
            "breaking_news_override": news_override,
            "editorial_lanes": ["top_gainers", "top_losers", "volume_leaders", "new_listings", "high_volatility", "BTC_ETH_market_context", "news_and_macro"],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
