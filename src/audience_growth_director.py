"""Audience-growth director for the single autonomous creator.

Chooses between evidence-backed opportunity posts and timely crypto-native meme
posts. Growth is optimized through legitimate content quality and learning, not
spam, fake engagement, or payment solicitation.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREF = ROOT / "data/live/editorial_preflight.json"
DIRECTOR = ROOT / "data/live/content_director_brief.json"
MARKET = ROOT / "data/live/market_snapshot.json"
NEWS = ROOT / "data/live/news_snapshot.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
OUT = ROOT / "data/live/audience_growth_director.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def rows(value):
    return value if isinstance(value, list) else []


def num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def symbol(value):
    s = str(value or "").upper().replace("$", "").replace("USDT", "").strip()
    return s


def choose_meme_candidate(market, news):
    candidates = []
    for item in rows(market.get("top_content_signals")) + rows(market.get("top_gainers")) + rows(market.get("top_losers")):
        if not isinstance(item, dict) or not symbol(item.get("symbol")):
            continue
        move = abs(num(item.get("price_change_percent")))
        signal = num(item.get("content_signal_score"))
        volume = num(item.get("quote_volume_usdt") or item.get("quote_volume"))
        score = min(100.0, move * 3.0 + signal * 0.5 + min(20.0, volume / 1e8 * 20))
        candidates.append((score, symbol(item.get("symbol")), item))
    for article in rows(news.get("articles")):
        if not isinstance(article, dict):
            continue
        title = str(article.get("title") or "").strip()
        if not title:
            continue
        for s in rows(article.get("symbols"))[:2]:
            if symbol(s):
                candidates.append((num(article.get("news_score"), 0) * 0.9, symbol(s), article))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0] if candidates else None


def main():
    pre = load(PREF)
    director = load(DIRECTOR)
    market = load(MARKET)
    news = load(NEWS)
    feedback = load(FEEDBACK)
    selected = pre.get("selected_opportunity") or {}

    if selected and str(selected.get("category") or "").lower() in {
        "capital_flow_long", "capital_flow_short", "technical_setup", "top_gainers",
        "top_losers", "high_volatility", "volume_leaders", "watchlist", "follow_up",
        "creator_signal_outcome", "news_and_macro", "breaking_news"
    }:
        mode = "OPPORTUNITY"
        rationale = "evidence-backed market opportunity takes priority over entertainment"
    else:
        candidate = choose_meme_candidate(market, news)
        mode = "MEME" if candidate and candidate[0] >= 38 else "WAIT"
        rationale = (
            "use a timely crypto-native meme to maintain audience relevance when no strong trade setup is ready"
            if mode == "MEME" else "no sufficiently timely meme or market opportunity"
        )
        if mode == "MEME":
            _, sym, source = candidate
            selected = {
                "category": "crypto_meme",
                "symbol": sym,
                "score": round(min(82.0, max(62.0, candidate[0])), 2),
                "lane": "audience_growth",
                "meme_source_type": "market_move" if source in rows(market.get("top_content_signals")) + rows(market.get("top_gainers")) + rows(market.get("top_losers")) else "news",
                "meme_context": str(source.get("title") or "")[:240] if isinstance(source, dict) else "",
            }
            pre["selected_opportunity"] = selected

    learned = feedback.get("learned_preferences") or {}
    result = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "selected": selected,
        "rationale": rationale,
        "growth_objectives": [
            "maximize qualified reach",
            "turn readers into returning followers through consistent useful series",
            "learn which formats create views, replies, shares and follower growth",
            "use memes for discovery without sacrificing the account's market-analysis identity",
        ],
        "content_rules": [
            "opportunity posts outrank memes whenever evidence is strong",
            "memes must remain crypto-relevant and original",
            "never manufacture wins, views, followers or engagement",
            "never use fake urgency or coordinated trading language",
            "never solicit payment, tips, donations or off-platform contact in posts",
            "track every published opportunity and its outcome before claiming success",
        ],
        "learning_inputs": {
            "learned_preferences_present": bool(learned),
            "feedback_keys": sorted(list(learned.keys())) if isinstance(learned, dict) else [],
        },
        "series_plan": {
            "opportunity": "SETUP -> CHART -> RESULT -> NEXT SETUP",
            "meme": "TIMELY MEME -> MARKET CONTEXT -> OPTIONAL FOLLOW-UP",
            "accountability": "ORIGINAL CALL -> LOCKED OUTCOME -> WIN/LOSS/INVALIDATED",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    pre["audience_growth_director"] = result
    PREF.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
