import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from google import genai

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TOPIC = os.getenv("TOPIC", "").strip()
OUTPUT_DIR = Path("data/reports")
LIVE_SNAPSHOT = Path("data/live/market_snapshot.json")
NEWS_SNAPSHOT = Path("data/live/news_snapshot.json")
PREFLIGHT = Path("data/live/editorial_preflight.json")
STRATEGY_MEMORY = Path("analytics/strategy_memory.json")
CREATOR_PATTERNS = Path("data/intelligence/creator_patterns.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = r'''You are the senior editorial intelligence of an original HUMAN crypto creator on Binance Square.
Use public creator research only as pattern intelligence. Never copy another creator's sentences, distinctive phrasing, identity, branding or posts. Do not claim to know Binance's hidden recommendation algorithm. Treat observed patterns as hypotheses and validate them against our own performance.

GOAL: maximize genuine attention, useful interaction, follower growth and eligible monetization opportunities without spam, fake engagement, fabricated facts or guaranteed returns.

MONETIZATION & ATTRIBUTION: Include the natural cashtag for the primary tradeable asset discussed (e.g. $TRUMP, $BTC, $ETH) in the text.
VISUAL-FIRST: For a single-asset market story, prefer a REAL Binance 1h candlestick chart. Use only real OHLCV-derived levels/patterns. Never invent a pattern or level.
WRITING: Normal target 180-500 characters; hard maximum 750. First line creates curiosity. Use 2-5 short mobile-friendly lines. Sound conversational, not like a financial report. Do not automatically provide TP/SL/entry calls.
INTERACTION: End with exactly ONE low-friction question answerable in under five seconds. Avoid generic "What do you think?" and never beg for likes/follows.
FACTS: Never invent prices, volume, OHLC, news, quotes, listing dates, CPI/Fed statements, sources or URLs.
Return ONLY valid JSON with research, critique, draft and visual_plan fields.'''


def load(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def normalize_object(value, fallback_key="text"):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {fallback_key: value}
    return {}


def normalize_draft(value):
    draft = normalize_object(value)
    draft.setdefault("text", "")
    draft.setdefault("quality_score", 0)
    draft.setdefault("editorial_style", "normalized")
    return draft


def normalize_visual(value):
    if isinstance(value, dict):
        value.setdefault("use_visual", value.get("type") not in (None, "none"))
        return value
    if isinstance(value, str):
        return {"type": value, "use_visual": value != "none"}
    return {"type": "none", "use_visual": False}


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise RuntimeError("Gemini returned non-object JSON")
    return value


def safe_slug_value(value):
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("symbol", "topic", "name", "title", "value"):
            candidate = value.get(key)
            if isinstance(candidate, (str, int, float)) and str(candidate).strip():
                return str(candidate)
    return ""


def all_market_items(market):
    items = []
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for item in market.get(group) or []:
            if isinstance(item, dict) and item.get("symbol"):
                items.append(item)
    return items


def find_item(market, symbol):
    target = str(symbol or "").upper().replace("USDT", "")
    for item in all_market_items(market):
        candidate = str(item.get("symbol", "")).upper().replace("USDT", "")
        if candidate == target:
            return item
    return next((x for x in all_market_items(market) if x.get("candles_1h")), None)


def fmt_money(value):
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.0f}K"
    return f"${value:.0f}"


def local_market_fallback(live, preflight, memory):
    selected = preflight.get("selected_opportunity") or {}
    item = find_item(live, selected.get("symbol"))
    if not item:
        return None
    symbol = str(item.get("symbol", "")).upper().replace("USDT", "")
    try:
        move = float(item.get("price_change_percent") or 0)
    except Exception:
        move = 0.0
    try:
        volume = max(0.0, float(item.get("quote_volume_usdt") or item.get("quote_volume") or 0))
    except Exception:
        volume = 0.0
    try:
        intraday = float(item.get("intraday_range_percent") or 0)
    except Exception:
        intraday = 0.0
    candles = item.get("candles_1h") or []
    closes = [float(c["close"]) for c in candles if c.get("close") is not None]
    highs = [float(c["high"]) for c in candles if c.get("high") is not None]
    lows = [float(c["low"]) for c in candles if c.get("low") is not None]
    last = float(item.get("last_price") or (closes[-1] if closes else 0))
    resistance = max(highs[-8:]) if highs else last
    support = min(lows[-8:]) if lows else last
    category = str(selected.get("category") or "market_opportunity").lower()
    styles = ["shock", "debate", "watchlist", "story", "technical"]
    style = styles[len(memory.get("recent_performance_observations") or []) % len(styles)]
    if category == "top_gainers":
        hook = f"${symbol} just woke up: {move:+.1f}% today."
        question = f"Would you chase ${symbol}, or wait for a pullback?"
    elif category == "top_losers":
        hook = f"${symbol} just got hit hard: {move:+.1f}% today."
        question = f"Capitulation or another leg down for ${symbol}?"
    elif category == "volume_leaders":
        hook = f"Something changed in ${symbol}: volume is suddenly {fmt_money(volume)}."
        question = f"Real rotation into ${symbol}, or just noise?"
    elif category == "new_listings":
        hook = f"New listing ${symbol} is already showing serious volatility."
        question = f"Would you watch ${symbol}, or wait for price to settle?"
    elif category == "high_volatility":
        hook = f"${symbol} is moving violently today — {move:+.1f}% with a {intraday:.1f}% range."
        question = "Breakout opportunity or volatility trap?"
    else:
        hook = f"${symbol} is making a move that deserves a closer look."
        question = f"Bullish setup or fakeout for ${symbol}?"
    if style == "debate":
        hook = f"The interesting part isn't the {move:+.1f}% move in ${symbol}. It's what happens next."
    elif style == "watchlist":
        hook = f"${symbol} just moved onto my watchlist. Here's why."
    elif style == "story":
        hook = f"One chart is telling a very different story today: ${symbol}."
    elif style == "technical":
        hook = f"${symbol}: the next few candles matter more than the headline move."
    price = f"Last: ${last:.8g}" if last else ""
    levels = f"Observed range: ${support:.8g}–${resistance:.8g}" if support and resistance else ""
    stats = f"{price} • {fmt_money(volume)} spot volume" if volume else price
    range_line = f"{intraday:.1f}% intraday range" if intraday else ""
    text = "\n".join(x for x in (hook, stats, range_line, levels, question) if x)
    return {
        "research": {"summary": "Quota-safe draft built only from the verified live market snapshot.", "strongest_signal": symbol, "source_mode": "local_fallback", "opportunity_score": float(selected.get("adjusted_score") or 80)},
        "critique": {"summary": "Gemini was unavailable; deterministic editorial fallback preserved verified market facts.", "reason": "gemini_quota_or_rate_limit", "revised_opportunity_score": float(selected.get("adjusted_score") or 80)},
        "draft": {"post": text[:740], "text": text[:740], "hook": hook, "discussion_question": question, "quality_score": 82, "editorial_style": f"fallback_{style}", "generation_mode": "LOCAL_FALLBACK"},
        "visual_plan": {"type": "candlestick_chart", "use_visual": bool(candles), "title": f"{symbol}: real 1H market structure", "data_points": [{"symbol": symbol}], "purpose": "Show real OHLCV structure, observed levels and detected patterns."}
    }


def local_news_fallback(news):
    articles = [x for x in (news.get("articles") or []) if isinstance(x, dict)]
    if not articles:
        return None
    article = articles[0]
    title = str(article.get("title") or article.get("headline") or "").strip()
    if not title:
        return None
    text = f"This is the crypto story I’m watching right now:\n{title}\n\nBullish catalyst or headline noise?"
    return {
        "research": {"summary": "Quota-safe news draft built from the latest supplied news snapshot.", "source_mode": "local_news_fallback", "opportunity_score": 80},
        "critique": {"summary": "Gemini unavailable; kept the supplied headline unchanged rather than inventing context.", "revised_opportunity_score": 80},
        "draft": {"post": text[:740], "text": text[:740], "hook": "This is the crypto story I’m watching right now:", "discussion_question": "Bullish catalyst or headline noise?", "quality_score": 78, "editorial_style": "fallback_news", "generation_mode": "LOCAL_FALLBACK"},
        "visual_plan": {"type": "none", "use_visual": False}
    }


def call_creator(client, prompt):
    response = client.interactions.create(model=MODEL, input=prompt, system_instruction=SYSTEM)
    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


def main():
    live = load(LIVE_SNAPSHOT)
    news = load(NEWS_SNAPSHOT)
    preflight = load(PREFLIGHT)
    memory = load(STRATEGY_MEMORY)
    creator_patterns = load(CREATOR_PATTERNS)
    selected = preflight.get("selected_opportunity") or {}

    if os.getenv("LOCAL_FALLBACK", "").lower() == "true":
        result = local_market_fallback(live, preflight, memory) or local_news_fallback(news)
        if not result:
            raise RuntimeError("Local fallback found neither a usable market opportunity nor a news article")
        generation_mode = "LOCAL_FALLBACK"
    else:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        client = genai.Client(api_key=key)
        engagement = preflight.get("engagement_strategy") or {}
        instruction = TOPIC or selected.get("instruction") or "Choose the strongest evidence-based opportunity across all supplied market and news lanes."
        prompt = (
            "EDITORIAL LANE:\n" + instruction +
            "\n\nOUR ENGAGEMENT STRATEGY:\n" + json.dumps(engagement, ensure_ascii=False, indent=2) +
            "\n\nPUBLIC CREATOR PATTERNS:\n" + json.dumps(creator_patterns, ensure_ascii=False, indent=2) +
            "\n\nPREFLIGHT:\n" + json.dumps(preflight, ensure_ascii=False, indent=2) +
            "\n\nLIVE MARKET:\n" + json.dumps(live, ensure_ascii=False, indent=2) +
            "\n\nNEWS:\n" + json.dumps(news, ensure_ascii=False, indent=2) +
            "\n\nOUR STRATEGY MEMORY:\n" + json.dumps(memory, ensure_ascii=False, indent=2) +
            "\n\nCreate ONE original short visual-first post."
        )
        result = parse_json(call_creator(client, prompt))
        generation_mode = "GEMINI"

    research = normalize_object(result.get("research"), "summary")
    critique = normalize_object(result.get("critique"), "summary")
    draft = normalize_draft(result.get("draft"))
    visual = normalize_visual(result.get("visual_plan"))
    draft["experiment_id"] = (preflight.get("engagement_strategy") or {}).get("experiment_id") or preflight.get("recommended_experiment") or "A"
    draft["symbol"] = selected.get("symbol") or research.get("strongest_signal") or ""
    draft["content_category"] = selected.get("category") or selected.get("reason") or "market_opportunity"
    draft["publication_status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    draft["generation_mode"] = generation_mode
    if not draft.get("post") and draft.get("text"):
        draft["post"] = str(draft["text"]).strip()
    allowed = {"candlestick_chart", "market_bar_chart", "market_comparison", "market_range_chart", "news_timeline", "text_card", "none"}
    if visual.get("type") not in allowed:
        visual["type"] = "none"
        visual["use_visual"] = False

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic_instruction": TOPIC or selected.get("instruction", ""),
        "selected_editorial_lane": selected,
        "engagement_strategy": preflight.get("engagement_strategy") or {},
        "creator_intelligence": creator_patterns,
        "live_market_snapshot": live,
        "news_discovery_snapshot": news,
        "strategy_memory": memory,
        "research": research,
        "critique": critique,
        "draft": draft,
        "visual_plan": visual,
        "status": "DRAFT_ONLY_NOT_PUBLISHED",
        "generation_mode": generation_mode,
        "gemini_requests_used": 1 if generation_mode == "GEMINI" else 0,
    }
    slug_source = TOPIC or safe_slug_value(research.get("strongest_signal")) or safe_slug_value(selected.get("category")) or "market-opportunity"
    slug = "".join(c.lower() if c.isalnum() else "-" for c in slug_source).strip("-")[:80] or "market-opportunity"
    output = OUTPUT_DIR / f"{slug}-multi-agent.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "DRAFT_ONLY_NOT_PUBLISHED", "report": str(output), "quality_score": draft.get("quality_score", 0), "editorial_style": draft.get("editorial_style", ""), "generation_mode": generation_mode, "visual_requested": visual.get("use_visual", False), "visual_type": visual.get("type", "none")}, indent=2))


if __name__ == "__main__":
    main()
