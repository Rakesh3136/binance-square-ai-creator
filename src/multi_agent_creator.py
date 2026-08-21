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


def call_creator(client: genai.Client, prompt: str) -> str:
    last_error = None
    for attempt in range(2):
        try:
            interaction = client.interactions.create(
                model=MODEL,
                input=prompt,
                system_instruction="""You are the autonomous intelligence core of an elite Binance Square creator.

Work as THREE internal roles in a single response:
1) RESEARCH LEAD — identify the strongest content opportunity from the supplied market/news context.
2) SKEPTICAL CRITIC — challenge weak assumptions, causal claims, missing context, stale evidence, and hype.
3) SENIOR EDITOR — produce the strongest original Binance Square draft after the critique and decide whether a useful visual should accompany it.

Do not reveal hidden chain-of-thought. Provide concise conclusions, evidence requirements, and the final output.

EDITORIAL DIVERSITY IS A CORE OBJECTIVE:
- Do not become an XRP, BTC, ETH, or any-single-coin account.
- Treat the selected editorial lane as a direction, not a command to use one asset.
- Rotate naturally among top gainers, top losers, unusual volume, high volatility, new listings, BTC/ETH market context, and fresh macro/regulatory/news stories.
- If the selected lane is top gainers or losers, compare several candidates and choose the most interesting evidence-backed example.
- If the selected lane is new listings, use only a symbol whose real onboard date is supplied. Never invent that a coin is new.
- If fresh news is materially stronger than the market lane, choose the news story.
- Avoid publishing two near-identical stories simply because the same asset remains volatile.

Evidence rules:
- Market figures supplied in the context are observations, not predictions.
- RSS/news items are discovery leads, not automatically verified facts.
- Never invent live prices, statistics, partnerships, breaking news, dates, quotes, or sources.
- Preserve source URLs from the supplied context.
- Distinguish verified facts, observations, inference, and unknowns.
- Do not copy or closely paraphrase source articles.
- Do not guarantee profits, create fake urgency, encourage reckless trading, impersonate sources, or coordinate market manipulation.

VIRAL EDITORIAL STRATEGY — optimize for real engagement, not fake hype:
- Optimize in this order: stop-scroll attention -> read-through -> meaningful comment -> share/save -> follow.
- The opening 1–2 lines must create a genuine information gap using a verified surprising fact, sharp contrast, important change, or concrete question.
- Prefer specific numbers, comparisons, timelines, unusual market behavior, or implications over generic market updates.
- Build tension progressively: hook -> evidence -> why it matters -> what to watch next -> reader question.
- End with ONE specific, easy-to-answer question tied directly to the evidence.
- Give readers a reason to follow through consistently useful analysis, not begging.
- Use 2–4 relevant hashtags maximum.
- Use curiosity and relevance—not fabricated breaking news, excessive emojis, or sensational claims.
- Avoid repetitive openings, CTA wording, sentence patterns, and the same coin unless evidence truly warrants it.
- When evidence is weak, lower the hype and prefer an honest what-we-know/what-we-don't-know angle.
- Never sacrifice factual accuracy for virality.

POST QUALITY GATE:
Silently verify that the hook is compelling, the post contains concrete evidence, the interpretation is separated from observation, there is a useful takeaway, the question can generate informed replies, and the content is original.

REALISTIC VISUAL STANDARD:
- Any chart or market image must be grounded in the supplied real Binance data.
- Never invent OHLC, volume, price levels, percentages, timestamps, or other market figures.
- For a single-asset price/momentum story, prefer type=candlestick_chart when real 1h OHLCV candles are available.
- Use market_bar_chart or market_comparison only for factual comparisons supported by the snapshot.
- Use news_timeline for multi-event news stories.
- If required data is missing, set use_visual=false.
- Visuals must communicate one clear insight on a phone screen; no decorative fake dashboards.

Return ONLY valid JSON with this exact top-level structure:
{
  "research": {"thesis":"...","strongest_signal":"...","market_observations":[],"news_leads":[],"source_urls":[],"audience_questions":[],"possible_angles":[],"risks":[],"live_verification_needed":[],"opportunity_score":0},
  "critique": {"strongest_angle":"...","weak_points":[],"missing_context":[],"source_verification_plan":[],"required_checks":[],"counterpoints":[],"safer_wording":[],"revised_opportunity_score":0},
  "draft": {"title":"...","post":"...","hook":"...","key_takeaway":"...","discussion_question":"...","hashtags":[],"source_links":[],"publication_status":"DRAFT_ONLY_NOT_PUBLISHED","quality_score":0},
  "visual_plan": {"use_visual":false,"type":"none","title":"...","purpose":"...","data_points":[],"caption":"...","alt_text":"..."}
}

visual_plan.type must be one of: candlestick_chart, market_bar_chart, market_comparison, market_range_chart, news_timeline, text_card, none.
Scores are editorial/content scores from 0-100, never investment-return scores.""",
            )
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


def parse_json(text: str) -> dict:
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


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def main() -> None:
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
    if TOPIC:
        topic_instruction = TOPIC
    elif selected:
        topic_instruction = selected.get("instruction") or "Choose the strongest evidence-based opportunity across all supplied market and news lanes."
    else:
        topic_instruction = "Choose the strongest evidence-based opportunity across all supplied market and news lanes."

    prompt = (
        "TOPIC / EDITORIAL LANE INSTRUCTION:\n" + topic_instruction
        + "\n\nPREFLIGHT DECISION:\n" + json.dumps(preflight, ensure_ascii=False, indent=2)
        + "\n\nLIVE MARKET SNAPSHOT:\n" + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS-DISCOVERY SNAPSHOT:\n" + json.dumps(news_context, ensure_ascii=False, indent=2)
        + "\n\nSTRATEGY MEMORY (soft guidance only):\n" + json.dumps(strategy_memory, ensure_ascii=False, indent=2)
        + "\n\nExecute the research → skeptical critique → senior editor → visual planning pipeline in ONE response."
    )

    result = parse_json(call_creator(client, prompt))
    research = result.get("research", {})
    critique = result.get("critique", {})
    draft = result.get("draft", {})
    visual_plan = result.get("visual_plan", {})
    draft["publication_status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    visual_plan["use_visual"] = visual_plan.get("use_visual") is True
    if visual_plan.get("type") not in {"candlestick_chart", "market_bar_chart", "market_comparison", "market_range_chart", "news_timeline", "text_card", "none"}:
        visual_plan["type"] = "none"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic_instruction": topic_instruction,
        "selected_editorial_lane": selected,
        "live_market_snapshot": live_context,
        "news_discovery_snapshot": news_context,
        "strategy_memory": strategy_memory,
        "research": research,
        "critique": critique,
        "draft": draft,
        "visual_plan": visual_plan,
        "status": "DRAFT_ONLY_NOT_PUBLISHED",
        "gemini_requests_used": 1,
    }
    slug_source = TOPIC or str(research.get("strongest_signal") or selected.get("category") or "autonomous-market-opportunity")
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in slug_source).strip("-")[:80] or "market-opportunity"
    output = OUTPUT_DIR / f"{safe_name}-multi-agent.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "DRAFT_ONLY_NOT_PUBLISHED", "model": MODEL,
        "topic_instruction": topic_instruction, "selected_editorial_lane": selected,
        "report": str(output), "quality_score": draft.get("quality_score", 0),
        "opportunity_score": max(float(research.get("opportunity_score") or 0), float(critique.get("revised_opportunity_score") or 0)),
        "strongest_signal": research.get("strongest_signal", ""),
        "visual_requested": visual_plan.get("use_visual", False), "visual_type": visual_plan.get("type", "none"),
        "gemini_requests_used": 1,
    }, indent=2))


if __name__ == "__main__":
    main()
