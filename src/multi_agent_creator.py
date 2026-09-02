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
WRITING: Target 300-700 characters for normal posts; hard maximum 900. Write like a sharp human crypto newsroom/editor, not a ticker bot. The first 1-2 lines must contain the concrete reason the story matters NOW. Use varied sentence length, specific nouns/verbs, and short mobile paragraphs. Never pad with "fresh check", "quick market check", or generic filler.
NEWS MODE: When the selected opportunity contains verified news, the post MUST be news-first: state the actual event, identify the source naturally, explain why it matters, then connect it to the affected asset/market. Never convert a news story into a generic percentage-move recap. For macro stories, explain the transmission into crypto. When no material news is selected, do not manufacture a news angle.
TECHNICAL MODE: When the story is a chart setup, explain the setup using current verified OHLCV evidence. Give support/resistance/trigger/target/invalidation only when supported. Prefer a clear bull/bear scenario over empty hype.
COMPARISON MODE: For related assets, build the narrative around the relationship (e.g. Gold vs Silver, BTC vs ETH) and use a pair of real TradingView charts when helpful. Never pretend the second asset is part of the catalyst unless verified.
INTERACTION: End with exactly ONE low-friction question that is specific to the story. Avoid generic "What do you think?" and never beg for likes/follows.
STYLE ROTATION: Do not reuse the same opening cadence, editorial_style, or paragraph structure as the immediately previous post. Rotate among NEWSROOM, ANALYST, CONVERSATIONAL, CONTRARIAN, DATA, COMPARISON, CHART CHALLENGE, LIQUIDATION STORY, BREAKOUT/FAKEOUT, FOLLOW-UP and MINI-STORY.
FACTS: Never invent prices, volume, OHLC, news, quotes, listing dates, CPI/Fed statements, sources, URLs, creator calls, targets or outcomes. If a fact is not in the supplied evidence, omit it.
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


def _previous_style(preflight):
    strategy = preflight.get("engagement_strategy") or {}
    counts = strategy.get("recent_style_counts") or {}
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


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
    engagement = preflight.get("engagement_strategy") or {}
    experiment = engagement.get("experiment") or {}
    exp_id = str(engagement.get("experiment_id") or selected.get("experiment_id") or "A").upper()
    exp_format = str(experiment.get("format") or "CHOICE").upper()
    previous_style = _previous_style(preflight)

    # Each experiment has a genuinely different fallback structure. This is
    # intentionally not driven by a simple counter, because a counter can keep
    # producing the same prose pattern when AI is unavailable for a long period.
    if exp_id == "A" or exp_format == "CHOICE":
        hook = f"${symbol} moved {move:+.1f}% today. The interesting part is what price does after the first impulse."
        detail = f"Last ${last:.8g} • {fmt_money(volume)} spot volume" if volume else f"Last ${last:.8g}"
        question = f"Would you chase ${symbol} now, or wait for a pullback?"
        style = "fallback_choice"
    elif exp_id == "B" or exp_format == "CHART CHALLENGE":
        hook = f"Quick chart challenge on ${symbol}: price is sitting after a {move:+.1f}% move."
        detail = f"Observed 1h range: ${support:.8g} → ${resistance:.8g}"
        question = "Which level would you mark first: the recent high or the recent low?"
        style = "fallback_chart_challenge"
    elif exp_id == "C" or exp_format == "COIN VS COIN":
        # Use one real comparison partner from the current market snapshot.
        partner = next((x for x in all_market_items(live) if str(x.get("symbol", "")).upper() != str(item.get("symbol", "")).upper() and x.get("price_change_percent") is not None), None)
        psym = str(partner.get("symbol", "BTC")).upper().replace("USDT", "") if partner else "BTC"
        try: pmove = float(partner.get("price_change_percent")) if partner else 0.0
        except Exception: pmove = 0.0
        hook = f"${symbol} vs ${psym}: one market move is clearly stronger right now."
        detail = f"${symbol} {move:+.1f}% | ${psym} {pmove:+.1f}%"
        question = f"Which chart would you watch next: ${symbol} or ${psym}?"
        style = "fallback_coin_vs_coin"
    elif exp_id == "D" or exp_format == "DATA SURPRISE":
        hook = f"The number that stands out on ${symbol}: {intraday:.1f}% intraday range."
        detail = f"Spot volume {fmt_money(volume)} • last ${last:.8g}"
        question = "Did you notice the volatility before looking at the headline move?"
        style = "fallback_data_surprise"
    elif exp_id == "E" or exp_format == "BREAKOUT OR FAKEOUT":
        hook = f"${symbol} is testing the edge of its recent range after a {move:+.1f}% move."
        detail = f"Resistance ${resistance:.8g} • support ${support:.8g}"
        question = "Breakout or fakeout?"
        style = "fallback_breakout_fakeout"
    elif exp_id == "F" or exp_format == "NEWS REACTION":
        hook = f"${symbol} has the market's attention today. Here's the price action I would watch."
        detail = f"{move:+.1f}% today • {fmt_money(volume)} spot volume" if volume else f"{move:+.1f}% today"
        question = "Bullish follow-through or headline fade?"
        style = "fallback_news_reaction"
    elif exp_id == "G" or exp_format == "LIQUIDATION STORY":
        hook = f"${symbol}: this move looks more like a flush than a quiet trend."
        detail = f"{intraday:.1f}% intraday range • ${support:.8g} low" if intraday else f"Observed low ${support:.8g}"
        question = "Reversal or continuation from here?"
        style = "fallback_liquidation_story"
    else:
        hook = f"Top-mover check: ${symbol} is up {move:+.1f}% with {fmt_money(volume)} in spot volume."
        detail = f"Last ${last:.8g} • range {intraday:.1f}%" if intraday else f"Last ${last:.8g}"
        question = f"Chase ${symbol}, fade it, or wait?"
        style = "fallback_top_movers"

    # Absolute anti-repetition guard: if the strategy reports the same style as
    # recent content, switch the structure without changing the market facts.
    if previous_style == style.upper():
        hook = f"One detail on ${symbol} is easy to miss: {intraday:.1f}% intraday range."
        detail = f"Last ${last:.8g} • {fmt_money(volume)} spot volume" if volume else f"Last ${last:.8g}"
        question = f"Is ${symbol} setting up, or simply getting noisy?"
        style = "fallback_quick_def local_news_fallback(news):
    articles = [x for x in (news.get("articles") or []) if isinstance(x, dict) and str(x.get("title") or "").strip()]
    if not articles:
        return None
    article = sorted(articles, key=lambda x: (float(x.get("news_score") or 0), str(x.get("published_at") or "")), reverse=True)[0]
    title = str(article.get("title") or "").strip()
    source = str(article.get("source") or "").strip()
    symbols = article.get("symbols") or []
    symbol = str(symbols[0] if symbols else "").upper().replace("USDT","")
    source_line = f"Source: {source}" if source else "Source: verified news feed"
    if symbol:
        hook = "🚨 $" + symbol + ": " + title
        visual = {"type":"candlestick_chart","use_visual":True}
    else:
        hook = "🚨 " + title
        visual = {"type":"market_comparison","use_visual":True}
    body = hook + "\n\n" + source_line + "\n\nWhy it matters: the market reaction is what we need to watch next."
    question = "Does this change your view on $" + symbol + "?" if symbol else "Headline catalyst or temporary noise?"
    text = (body + "\n\n" + question)[:880]
    return {
        "research": {"summary":"Fresh verified headline selected from news snapshot.", "source_mode":"local_news_fallback", "strongest_signal":symbol or "macro", "opportunity_score":90},
        "critique": {"summary":"News-first fallback preserved the supplied event and source without inventing details.", "revised_opportunity_score":90},
        "draft": {"post":text,"text":text,"hook":hook,"discussion_question":question,"quality_score":86,"editorial_style":"fallback_newsroom","generation_mode":"LOCAL_FALLBACK","symbol":symbol},
        "visual_plan": visual
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
            "\n\nCreate ONE original short visual-first post. It must use a visibly different editorial structure from the previous post and follow the selected experiment."
        )
        result = parse_json(call_creator(client, prompt))
        generation_mode = "GEMINI"

    research = normalize_object(result.get("research"), "summary")
    critique = normalize_object(result.get("critique"), "summary")
    draft = normalize_draft(result.get("draft"))
    visual = normalize_visual(result.get("visual_plan"))
    draft["experiment_id"] = (preflight.get("engagement_strategy") or {}).get("experiment_id") or preflight.get("recommended_experiment") or "A"
    draft["experiment_format"] = ((preflight.get("engagement_strategy") or {}).get("experiment") or {}).get("format")
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
