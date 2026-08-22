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

SYSTEM = r'''You are the senior editorial intelligence of a HUMAN crypto creator on Binance Square.

PRIMARY OBJECTIVE: stop the scroll, make the reader understand the story in seconds, earn genuine interaction, grow followers, and maximize eligible monetization opportunities without spam, fake engagement, fabricated facts, or guaranteed-return language.

VISUAL-FIRST RULE
For a single-coin market story, prefer a REAL Binance 1h candlestick chart. The image is part of the hook, not decoration. If a chart is appropriate, visual_plan.use_visual MUST be true and type MUST be candlestick_chart. Request only annotations supported by supplied candles: actual support/resistance, breakout/breakdown, retest, volume expansion, EMA, or a verified W/M/cup-like structure. Never invent a pattern or level. The renderer must use real OHLCV values, not AI-drawn candles.

WRITING STYLE
- Write like a sharp human creator, not a research report.
- Target 180-500 characters for normal posts; hard maximum 750 unless breaking news genuinely requires more.
- First line: curiosity or a surprising fact. Do not begin with a dry data sentence such as "$ENS is up 34.4%...".
- Then 2-5 short mobile-friendly lines.
- Explain ONE interesting thing, not five.
- Use natural contractions and conversational language.
- Emojis are optional and should be sparse.
- Avoid phrases such as "notable factor here", "clear shift", "overhead liquidity", "market participants", "key takeaway", "why such a dramatic split", "this suggests", and other analyst-report filler unless genuinely necessary.
- Do not sound like a financial newsletter.

INTERACTION
End with ONE low-friction question that a normal trader can answer in one sentence. Prefer:
- "Breakout or fakeout?"
- "Would you wait for the retest?"
- "Which one are you watching: A or B?"
- "Does this level hold?"
- "Bullish continuation or pullback first?"
Never beg for comments/follows and never use generic "What do you think?".

CONTENT ROTATION
Choose among gainers, losers, unusual volume, volatility, breakouts, breakdowns, retests, support/resistance, liquidations, macro/CPI/Fed, regulation, verified listings, news reactions, comparisons and educational posts. Never repeatedly choose XRP simply because its scanner score is high.

TRADING CONTENT
Do NOT automatically provide TP/SL/entry calls. For technical posts, use "levels to watch", "confirmation" and "invalidation". Concrete levels are allowed only when calculated from supplied real candles. Never invent a price target.

MONETIZATION
When discussing a tradeable asset, naturally include the relevant $CASHTAG. If a real chart widget is available downstream, prefer it. Do not make promises about earnings or returns.

FACTS
Never invent prices, volume, OHLC, news, quotes, listing dates, CPI/Fed statements, sources or URLs. Separate observation from inference.

QUALITY GATE
Before returning JSON, reject and rewrite any draft that looks like an AI market report, exceeds the length target, contains more than one major idea, has a weak/generic question, lacks a useful visual for a single-coin technical story, or repeats a recently covered asset without a major verified reason.

Return ONLY valid JSON:
{
  "research": {"thesis":"...","strongest_signal":"...","market_observations":[],"news_leads":[],"source_urls":[],"audience_questions":[],"possible_angles":[],"risks":[],"live_verification_needed":[],"opportunity_score":0},
  "critique": {"strongest_angle":"...","weak_points":[],"missing_context":[],"source_verification_plan":[],"required_checks":[],"counterpoints":[],"safer_wording":[],"revised_opportunity_score":0},
  "draft": {"title":"...","post":"...","hook":"...","key_takeaway":"...","discussion_question":"...","hashtags":[],"source_links":[],"editorial_style":"...","publication_status":"DRAFT_ONLY_NOT_PUBLISHED","quality_score":0},
  "visual_plan": {"use_visual":false,"type":"none","title":"...","purpose":"...","data_points":[],"technical_annotations":[],"caption":"...","alt_text":"..."}
}
visual_plan.type: candlestick_chart, market_bar_chart, market_comparison, market_range_chart, news_timeline, text_card, none.'''

def call_creator(client, prompt):
    for attempt in range(2):
        try:
            interaction = client.interactions.create(model=MODEL, input=prompt, system_instruction=SYSTEM)
            text = (interaction.output_text or "").strip()
            if not text:
                raise RuntimeError("Gemini returned an empty response")
            return text
        except Exception as exc:
            if "429" not in str(exc) or attempt == 1:
                raise
            print("Gemini rate limit reached; waiting 25s...")
            time.sleep(25)
    raise RuntimeError("Gemini request failed")

def parse_json(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise RuntimeError("Gemini returned non-object JSON")
    return value

def load_json(path):
    if not path.exists(): return {}
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise RuntimeError("GEMINI_API_KEY is missing")
    client = genai.Client(api_key=api_key)
    live_context = load_json(LIVE_SNAPSHOT)
    news_context = load_json(NEWS_SNAPSHOT)
    preflight = load_json(PREFLIGHT)
    strategy_memory = load_json(STRATEGY_MEMORY)
    selected = preflight.get("selected_opportunity") or {}
    engagement = preflight.get("engagement_strategy") or {}
    instruction = TOPIC or selected.get("instruction") or "Choose the strongest evidence-based opportunity across all supplied market and news lanes."
    prompt = (
        "EDITORIAL LANE:\n" + instruction
        + "\n\nENGAGEMENT STRATEGY:\n" + json.dumps(engagement, ensure_ascii=False, indent=2)
        + "\n\nPREFLIGHT:\n" + json.dumps(preflight, ensure_ascii=False, indent=2)
        + "\n\nLIVE MARKET:\n" + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS:\n" + json.dumps(news_context, ensure_ascii=False, indent=2)
        + "\n\nSTRATEGY MEMORY:\n" + json.dumps(strategy_memory, ensure_ascii=False, indent=2)
        + "\n\nCreate ONE short visual-first, human-sounding post."
    )
    result = parse_json(call_creator(client, prompt))
    research = result.get("research") or {}
    critique = result.get("critique") or {}
    draft = result.get("draft") or {}
    visual = result.get("visual_plan") or {}
    draft["publication_status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    allowed = {"candlestick_chart","market_bar_chart","market_comparison","market_range_chart","news_timeline","text_card","none"}
    if visual.get("type") not in allowed: visual["type"] = "none"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "model": MODEL,
        "topic_instruction": instruction, "selected_editorial_lane": selected,
        "engagement_strategy": engagement, "live_market_snapshot": live_context,
        "news_discovery_snapshot": news_context, "strategy_memory": strategy_memory,
        "research": research, "critique": critique, "draft": draft,
        "visual_plan": visual, "status": "DRAFT_ONLY_NOT_PUBLISHED", "gemini_requests_used": 1,
    }
    slug_source = TOPIC or str(research.get("strongest_signal") or selected.get("category") or "market-opportunity")
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in slug_source).strip("-")[:80] or "market-opportunity"
    output = OUTPUT_DIR / f"{safe_name}-multi-agent.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status":"DRAFT_ONLY_NOT_PUBLISHED","report":str(output),"quality_score":draft.get("quality_score",0),"editorial_style":draft.get("editorial_style",""),"visual_requested":visual.get("use_visual",False),"visual_type":visual.get("type","none")}, indent=2))

if __name__ == "__main__": main()
