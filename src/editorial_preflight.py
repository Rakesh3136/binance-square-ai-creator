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
ASSET_COOLDOWN_HOURS = 12


def load(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def extract_symbols(text):
    text = str(text or "").upper()
    found = set()
    for token in re.findall(r"(?<![A-Z0-9])\$?[A-Z][A-Z0-9]{1,11}(?:USDT)?(?![A-Z0-9])", text):
        clean = token.replace("$", "")
        base = clean[:-4] if clean.endswith("USDT") else clean
        if 2 <= len(base) <= 10:
            found.add(base)
    return found


def recent_publications():
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
            raw = " ".join(str(row.get(k) or "") for k in ("symbol", "selected_lane_symbol", "topic"))
            rows.append({**row, "_symbols": extract_symbols(raw), "_dt": dt})
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
    if category in {"top_gainers", "top_losers"}:
        raw_score = min(100.0, abs(float(item.get("price_change_percent") or 0)) * 4.5 + float(item.get("intraday_range_percent") or 0))
    elif category == "volume_leaders":
        raw_score = min(100.0, float(item.get("content_signal_score") or 0) + 10.0)
    elif category == "new_listings":
        age_bonus = max(0.0, 25.0 - float(item.get("days_since_listing") or 30) * 3.0)
        raw_score = min(100.0, float(item.get("content_signal_score") or 0) + age_bonus)
    raw_score = min(100.0, raw_score + score_boost)
    pool.append({
        "type": "market", "category": category, "topic": symbol,
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
    publications = recent_publications()

    market_items = market.get("top_content_signals") or []
    publication_counts = Counter()
    category_counts = Counter()
    last_asset_time = {}
    for row in publications:
        for symbol in row.get("_symbols", set()):
            publication_counts[symbol] += 1
            last_asset_time[symbol] = max(last_asset_time.get(symbol, datetime.min.replace(tzinfo=timezone.utc)), row["_dt"])
        if row.get("content_category"):
            category_counts[str(row["content_category"]).lower()] += 1
    memory_counts = memory_topics(memory)

    pool = []
    for item in (market.get("top_gainers") or [])[:10]: add_market_candidate(pool, "top_gainers", item)
    for item in (market.get("top_losers") or [])[:10]: add_market_candidate(pool, "top_losers", item)
    for item in (market.get("highest_volume") or [])[:10]: add_market_candidate(pool, "volume_leaders", item)
    for item in (market.get("new_listing_market") or [])[:10]: add_market_candidate(pool, "new_listings", item, 5.0)
    for item in sorted(market_items, key=lambda x: float(x.get("intraday_range_percent") or 0), reverse=True)[:8]: add_market_candidate(pool, "high_volatility", item, 3.0)
    for item in [x for x in market_items if str(x.get("symbol") or "") in {"BTCUSDT", "ETHUSDT"}]: add_market_candidate(pool, "BTC_ETH_market_context", item, 4.0)

    unique = {(c["category"], c["topic"]): c for c in pool}
    pool = list(unique.values())

    now = datetime.now(timezone.utc)
    for candidate in pool:
        base = candidate["topic"][:-4] if candidate["topic"].endswith("USDT") else candidate["topic"]
        recent_count = publication_counts.get(base, 0)
        cooldown = last_asset_time.get(base)
        cooldown_active = bool(cooldown and now - cooldown < timedelta(hours=ASSET_COOLDOWN_HOURS))
        pub_penalty = min(55.0, recent_count * 22.0)
        mem_penalty = min(54.0, memory_counts.get(base, 0) * MEMORY_REPEAT_PENALTY)
        cat_penalty = min(35.0, category_counts.get(candidate["category"], 0) * CATEGORY_REPEAT_PENALTY)
        candidate["recent_count"] = recent_count
        candidate["memory_count"] = memory_counts.get(base, 0)
        candidate["category_recent_count"] = category_counts.get(candidate["category"], 0)
        candidate["cooldown_active"] = cooldown_active
        candidate["adjusted_score"] = round(candidate["raw_score"] - pub_penalty - mem_penalty - cat_penalty - (45.0 if cooldown_active else 0.0), 2)
        candidate["repeated"] = recent_count >= 2 or memory_counts.get(base, 0) >= MEMORY_HARD_BLOCK_COUNT or cooldown_active

    fresh_news = 0
    for article in news.get("articles") or []:
        try:
            dt = datetime.fromisoformat(str(article.get("published_at", "")).replace("Z", "+00:00"))
            if now - dt <= timedelta(minutes=NEWS_FRESH_MINUTES):
                fresh_news += 1
        except Exception:
            continue

    # Pick the strongest candidate while actively preferring a different asset/category.
    eligible = [c for c in pool if not c["repeated"]]
    if not eligible:
        eligible = [c for c in pool if c["adjusted_score"] > 0]
    best = max(eligible, key=lambda x: x["adjusted_score"], default=None)
    market_ok = bool(best and best["adjusted_score"] >= MIN_MARKET_SCORE)
    run_ai = market_ok or fresh_news > 0
    reason = "fresh_news" if fresh_news > 0 and not market_ok else ("strong_market_opportunity" if market_ok else "no_strong_opportunity")

    selected = None
    if best:
        selected = {
            "category": best["category"], "symbol": best["topic"], "reason": best["reason"],
            "instruction": (
                f"Use the {best['category'].replace('_', ' ')} lane as the starting point, but compare the supplied candidates. "
                f"Do not publish {best['topic']} merely because it has the highest raw score; avoid any asset recently covered. "
                "Prefer a materially different asset, angle, and format when the evidence supports it. Fresh news may override market repetition."
            ),
        }

    result = {
        "generated_at": now.isoformat(), "run_ai": run_ai, "reason": reason,
        "selected_opportunity": selected,
        "candidate_pool": sorted(pool, key=lambda x: x["adjusted_score"], reverse=True)[:24],
        "best_market_candidate": best, "fresh_news_count": fresh_news,
        "recent_topic_counts": dict(publication_counts), "recent_category_counts": dict(category_counts),
        "memory_topic_counts": dict(memory_counts), "strategy_memory_loaded": bool(memory),
        "rules": {
            "min_market_score": MIN_MARKET_SCORE, "asset_cooldown_hours": ASSET_COOLDOWN_HOURS,
            "memory_repeat_penalty": MEMORY_REPEAT_PENALTY, "memory_hard_block_count": MEMORY_HARD_BLOCK_COUNT,
            "category_repeat_penalty": CATEGORY_REPEAT_PENALTY, "breaking_news_override": fresh_news > 0,
            "editorial_lanes": ["top_gainers", "top_losers", "volume_leaders", "new_listings", "high_volatility", "BTC_ETH_market_context", "news_and_macro"],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
