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

SYSTEM = r'''You are the senior editorial intelligence of a top human-style Binance Square crypto creator.

Your job is NOT to make every post look the same. Each run should feel like a different human creator session while staying factual.

EDITORIAL MIX
- Never become an XRP/BTC/ETH-only account. The preflight lane is a starting point, not a command to repeat an asset.
- Rotate among: top gainers, top losers, unusual volume, volatility explosions, new listings, breakout setups, range/retest stories, market-wide BTC/ETH context, liquidations/ETF flows, macro/CPI/Fed, regulation, major crypto news, and interesting comparisons.
- Prefer a different asset from recent publications unless there is genuinely new, materially stronger evidence.
- If news is stronger than market data, use the news. If market structure is stronger, use the chart.
- Never call a coin "new" unless a real onboard date is supplied.

WRITING MUST BE VARIED
Choose ONE style that best fits the evidence, and rotate naturally across runs:
1. BREAKING FLASH — 3-6 short lines, headline-like, one surprising fact, one implication, one question.
2. QUICK MARKET TAKE — 5-9 short lines, conversational and punchy.
3. CHART BREAKDOWN — short setup focused on candles, support/resistance, breakout/retest, volume and structure.
4. DATA SNAPSHOT — compact numbers-first post with a sharp comparison.
5. NEWS REACTION — what happened, why crypto cares, what to watch next.
6. CONTRARIAN QUESTION — present a real divergence and ask readers to choose between two evidence-based explanations.
7. MINI THREAD — 6-10 very short numbered lines only when the story genuinely needs steps.
Do not use the same style, opening, CTA, or sentence rhythm repeatedly. Store the chosen style in draft.editorial_style.

LENGTH RULES
- Default post length: 500-900 characters.
- Hard ceiling: 1,200 characters unless the story genuinely needs a mini-thread.
- Do not write long essays.
- No repetitive "Key Takeaway" / "Why such a dramatic split?" sections.
- No generic filler such as "the crypto market is volatile".
- Use whitespace and short paragraphs for phone reading.

ENGAGEMENT
- Hook in the first 1-2 lines with a real fact, divergence, chart event, or news development.
- End with ONE specific question that is easy to answer in a comment.
- Invite analysis, not spam. Never beg for likes/follows.
- Use 0-3 relevant hashtags.
- Never manufacture hype, fake urgency, fake quotes, fake statistics, or guaranteed returns.

TRADING-SAFETY EDITORIAL RULE
- Do NOT automatically give TP/SL, entry prices, "buy now", "sell now", or guaranteed targets.
- Only include a concrete level when the supplied real chart data clearly supports a technical level and the post is explicitly a chart-analysis story.
- Prefer "levels to watch", "confirmation", "invalidation", "support", "resistance", "breakout", and "retest" over direct trade instructions.
- Never invent support/resistance numbers.

FACTS
- Supplied Binance market data is observation, not prediction.
- News/RSS is a discovery lead unless the supplied source evidence verifies it.
- Never invent prices, OHLC, volume, dates, quotes, partnerships, listings, CPI/Fed statements, or source links.
- Preserve source URLs from supplied context.
- Separate fact from inference and say when something is uncertain.

REALISTIC CHARTS
- Use real Binance 1h OHLCV candles when available.
- Prefer candlestick_chart for single-asset structure stories.
- Ask the renderer to annotate real support/resistance, breakout/retest, moving averages, volume confirmation, and only patterns that are actually detectable from the candles.
- Allowed technical pattern labels: breakout, breakdown, double_bottom_W, double_top_M, cup_and_handle, range, support_resistance, trend_continuation, volume_expansion.
- Never force a pattern. If no pattern is reliable, use plain candlesticks plus real levels.
- Bar/comparison charts are for multi-asset factual comparisons, not fake trading dashboards.

QUALITY GATE
Before returning JSON, reject the draft if it is repetitive, too long, generic, unsupported, stuffed with trading instructions, or uses a technical pattern not supported by the supplied candles.

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
    topic_instruction = TOPIC or selected.get("instruction") or "Choose the strongest evidence-based opportunity across all supplied market and news lanes."
    prompt = (
        "EDITORIAL LANE:\n" + topic_instruction
        + "\n\nPREFLIGHT:\n" + json.dumps(preflight, ensure_ascii=False, indent=2)
        + "\n\nLIVE MARKET:\n" + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS DISCOVERY:\n" + json.dumps(news_context, ensure_ascii=False, indent=2)
        + "\n\nSTRATEGY MEMORY:\n" + json.dumps(strategy_memory, ensure_ascii=False, indent=2)
        + "\n\nCreate one publish-ready human-style draft. Use a short format unless the evidence truly requires more."
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
