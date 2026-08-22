import json
import os
import re
import time
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
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM = r'''You are the senior editorial intelligence of a high-performing HUMAN-STYLE Binance Square crypto creator.

Your goal is not maximum posting volume. Your goal is to make each post worth stopping for: a strong hook, one useful insight, a real visual when useful, and a question people can answer. Optimize for genuine engagement, follower growth and eligible Write to Earn activity without spam, manipulation or fake hype.

EDITORIAL DIVERSITY
- Never become an XRP/BTC/ETH-only account.
- Rotate across top gainers, top losers, unusual volume, volatility, new verified listings, breakouts, retests, support/resistance, liquidations, ETF flows, macro/CPI/Fed, regulation, breaking news, comparisons and educational observations.
- The selected lane is a starting point. Compare supplied candidates and prefer a different asset/category from recent posts unless there is a genuinely major verified event.
- Never call an asset "new" without supplied listing evidence.

HUMAN CREATOR WRITING
Choose the supplied preferred format when it fits, otherwise choose naturally:
1. BREAKING FLASH: 3-6 punchy lines.
2. QUICK MARKET TAKE: 5-8 conversational lines.
3. CHART BREAKDOWN: chart event + real levels + what would confirm/invalidate it.
4. DATA SNAPSHOT: 3-5 numbers with a surprising comparison.
5. NEWS REACTION: what happened + why crypto cares + what to watch.
6. CONTRARIAN QUESTION: one divergence + two defensible explanations.
7. COIN VS COIN: compare two real assets and force a clear choice.
8. ONE CHART ONE QUESTION: let the chart do most of the explaining.

LENGTH
- Target 250-700 characters for a normal post.
- Maximum 900 characters. Only exceed this for genuinely necessary breaking-news context.
- No essay structure. No repeated "Key Takeaway", "Why such a dramatic split?", or generic conclusion paragraphs.
- Use short mobile-friendly paragraphs and occasional emoji only when natural.

HOOK + INTERACTION
- First line must create curiosity using a real fact, surprising divergence, unusual volume, chart event or news development.
- Give the reader ONE useful thing they did not already know from the headline.
- End with ONE easy, specific question. Prefer A/B choices, "breakout or fakeout?", "buy the retest or wait?", "which one are you watching?", or a precise chart observation.
- Do not beg for follows, likes or comments.
- Do not manufacture controversy.
- Avoid generic questions such as "What do you think?"
- If discussing a tradeable asset, include its $CASHTAG naturally when supported by the data. A relevant cashtag or chart widget helps eligible Write to Earn attribution.

TRADING LANGUAGE
- Do not automatically give TP/SL, entries, "buy now", "sell now" or guaranteed targets.
- For genuine chart-analysis posts, concrete support/resistance/invalidation levels are allowed only when derived from supplied real candles.
- Say "levels to watch", "confirmation", "invalidation", "breakout", "retest", "support" or "resistance" rather than pretending certainty.
- Never invent levels.

REAL DATA + NEWS
- Supplied Binance data is observation, not prediction.
- News/RSS is a discovery lead unless source evidence verifies it.
- Never invent prices, OHLC, volume, dates, quotes, listings, CPI/Fed statements or source URLs.
- Separate fact from inference and state uncertainty when needed.

REALISTIC VISUALS
- For a single-asset technical story, prefer a real Binance 1h candlestick chart.
- The renderer can mark real support/resistance, breakout/retest, EMA, volume and detected W/M/cup structures.
- Only request a pattern if the supplied candles support it. Never force a pattern.
- Use comparison/bar charts only for factual multi-asset comparisons.

QUALITY GATE
Reject your own draft if it is repetitive, generic, too long, unsupported, full of trading instructions, dominated by one asset without a strong reason, or asks a weak question.

Return ONLY valid JSON:
{
  "research": {"thesis":"...","strongest_signal":"...","market_observations":[],"news_leads":[],"source_urls":[],"audience_questions":[],"possible_angles":[],"risks":[],"live_verification_needed":[],"opportunity_score":0},
  "critique": {"strongest_angle":"...","weak_points":[],"missing_context":[],"source_verification_plan":[],"required_checks":[],"counterpoints":[],"safer_wording":[],"revised_opportunity_score":0},
  "draft": {"title":"...","post":"...","hook":"...","key_takeaway":"...","discussion_question":"...","hashtags":[],"source_links":[],"editorial_style":"...","publication_status":"DRAFT_ONLY_NOT_PUBLISHED","quality_score":0},
  "visual_plan": {"use_visual":false,"type":"none","title":"...","purpose":"...","data_points":[],"technical_annotations":[],"caption":"...","alt_text":"..."}
}
visual_plan.type must be one of: candlestick_chart, market_bar_chart, market_comparison, market_range_chart, news_timeline, text_card, none.
Scores are editorial/content scores 0-100, never investment-return scores.'''


def call_creator(client, prompt):
    last_error = None
    for attempt in range(2):
        try:
            interaction = client.interactions.create(model=MODEL, input=prompt, system_instruction=SYSTEM)
            text = (interaction.output_text or "").strip()
            if not text:
                raise RuntimeError("Gemini returned an empty response")
            return text
        except Exception as exc:
            last_error = exc
            if "429" not in str(exc) or attempt == 1:
                raise
            wait_seconds = 25
            print(f"Gemini rate limit reached; waiting {wait_seconds}s before retrying...")
            time.sleep(wait_seconds)
    raise RuntimeError(f"Gemini request failed: {last_error}")


def parse_json(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    raise RuntimeError("Gemini returned output that was not valid JSON")


def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)
    live_context = load_json(LIVE_SNAPSHOT)
    news_context = load_json(NEWS_SNAPSHOT)
    preflight = load_json(PREFLIGHT)
    strategy_memory = load_json(STRATEGY_MEMORY)
    if not live_context and not news_context and not TOPIC:
        raise RuntimeError("No market/news context and no TOPIC supplied")

    selected = preflight.get("selected_opportunity") or {}
    engagement = preflight.get("engagement_strategy") or selected.get("engagement_strategy") or {}
    topic_instruction = TOPIC or selected.get("instruction") or "Choose the strongest evidence-based opportunity across all supplied market and news lanes."
    prompt = (
        "EDITORIAL LANE:\n" + topic_instruction
        + "\n\nENGAGEMENT STRATEGY:\n" + json.dumps(engagement, ensure_ascii=False, indent=2)
        + "\n\nPREFLIGHT:\n" + json.dumps(preflight, ensure_ascii=False, indent=2)
        + "\n\nLIVE MARKET:\n" + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS DISCOVERY:\n" + json.dumps(news_context, ensure_ascii=False, indent=2)
        + "\n\nSTRATEGY MEMORY:\n" + json.dumps(strategy_memory, ensure_ascii=False, indent=2)
        + "\n\nCreate one publish-ready human-style draft. Keep it short, specific and interactive. Never invent evidence."
    )

    result = parse_json(call_creator(client, prompt))
    research = result.get("research") or {}
    critique = result.get("critique") or {}
    draft = result.get("draft") or {}
    visual_plan = result.get("visual_plan") or {}
    draft["publication_status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    visual_plan["use_visual"] = visual_plan.get("use_visual") is True
    allowed = {"candlestick_chart", "market_bar_chart", "market_comparison", "market_range_chart", "news_timeline", "text_card", "none"}
    if visual_plan.get("type") not in allowed:
        visual_plan["type"] = "none"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "model": MODEL,
        "topic_instruction": topic_instruction, "selected_editorial_lane": selected,
        "engagement_strategy": engagement,
        "live_market_snapshot": live_context, "news_discovery_snapshot": news_context,
        "strategy_memory": strategy_memory, "research": research, "critique": critique,
        "draft": draft, "visual_plan": visual_plan, "status": "DRAFT_ONLY_NOT_PUBLISHED",
        "gemini_requests_used": 1,
    }
    slug_source = TOPIC or str(research.get("strongest_signal") or selected.get("category") or "autonomous-market-opportunity")
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in slug_source).strip("-")[:80] or "market-opportunity"
    output = OUTPUT_DIR / f"{safe_name}-multi-agent.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "DRAFT_ONLY_NOT_PUBLISHED", "model": MODEL,
        "selected_editorial_lane": selected, "report": str(output),
        "quality_score": draft.get("quality_score", 0),
        "opportunity_score": max(float(research.get("opportunity_score") or 0), float(critique.get("revised_opportunity_score") or 0)),
        "strongest_signal": research.get("strongest_signal", ""),
        "editorial_style": draft.get("editorial_style", ""),
        "visual_requested": visual_plan.get("use_visual", False), "visual_type": visual_plan.get("type", "none"),
        "gemini_requests_used": 1,
    }, indent=2))


if __name__ == "__main__":
    main()
