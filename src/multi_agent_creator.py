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
STRATEGY_MEMORY = Path("analytics/strategy_memory.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def call_creator(client: genai.Client, prompt: str) -> str:
    """One Gemini request per run, with bounded retry for transient rate limits."""
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

Evidence rules:
- Market figures supplied in the context are observations, not predictions.
- RSS/news items are discovery leads, not automatically verified facts.
- Never invent live prices, statistics, partnerships, breaking news, dates, quotes, or sources.
- Preserve source URLs from the supplied context.
- Distinguish verified facts, observations, inference, and unknowns.
- Do not copy or closely paraphrase source articles.
- Do not guarantee profits, create fake urgency, encourage reckless trading, impersonate sources, or coordinate market manipulation.

Content goal:
Create something genuinely useful and interesting for Binance Square readers, not generic market commentary.
Favor a specific insight, strong hook, clear context, and a thoughtful closing question.

Learning rules:
- Use the supplied strategy memory as a soft preference, not as proof that a topic will perform.
- Never sacrifice evidence quality, originality, or factual caution to imitate past winners.

Return ONLY valid JSON with this exact top-level structure:
{
  "research": {
    "thesis": "...",
    "strongest_signal": "...",
    "market_observations": [],
    "news_leads": [],
    "source_urls": [],
    "audience_questions": [],
    "possible_angles": [],
    "risks": [],
    "live_verification_needed": [],
    "opportunity_score": 0
  },
  "critique": {
    "strongest_angle": "...",
    "weak_points": [],
    "missing_context": [],
    "source_verification_plan": [],
    "required_checks": [],
    "counterpoints": [],
    "safer_wording": [],
    "revised_opportunity_score": 0
  },
  "draft": {
    "title": "...",
    "post": "...",
    "hook": "...",
    "key_takeaway": "...",
    "discussion_question": "...",
    "hashtags": [],
    "source_links": [],
    "publication_status": "DRAFT_ONLY_NOT_PUBLISHED",
    "quality_score": 0
  },
  "visual_plan": {
    "use_visual": false,
    "type": "none",
    "title": "...",
    "purpose": "...",
    "data_points": [],
    "caption": "...",
    "alt_text": "..."
  }
}

For visual_plan:
- use_visual=true only when a visual adds real information.
- type must be one of: market_bar_chart, market_comparison, market_range_chart, news_timeline, text_card, none.
- Use only data present in the supplied snapshots; never invent numbers.
- Prefer charts or comparisons for market-data stories and a timeline for multi-event news stories.
- If the story cannot be visualized honestly from the supplied context, set use_visual=false and type=none.

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
    strategy_memory = load_json(STRATEGY_MEMORY)

    if not live_context and not news_context and not TOPIC:
        raise RuntimeError("No market/news context and no TOPIC supplied")

    topic_instruction = TOPIC or (
        "Choose the single strongest Binance Square content opportunity from the live market and "
        "news-discovery snapshots. Prefer a specific, evidence-aware story over a generic price recap."
    )

    prompt = (
        "TOPIC INSTRUCTION:\n"
        + topic_instruction
        + "\n\nLIVE MARKET SNAPSHOT:\n"
        + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS-DISCOVERY SNAPSHOT:\n"
        + json.dumps(news_context, ensure_ascii=False, indent=2)
        + "\n\nSTRATEGY MEMORY (soft guidance only):\n"
        + json.dumps(strategy_memory, ensure_ascii=False, indent=2)
        + "\n\nExecute the research → skeptical critique → senior editor → visual planning pipeline in ONE response."
    )

    result = parse_json(call_creator(client, prompt))
    research = result.get("research", {})
    critique = result.get("critique", {})
    draft = result.get("draft", {})
    visual_plan = result.get("visual_plan", {})

    draft["publication_status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    if visual_plan.get("use_visual") not in (True, False):
        visual_plan["use_visual"] = False
    if visual_plan.get("type") not in {
        "market_bar_chart", "market_comparison", "market_range_chart", "news_timeline", "text_card", "none"
    }:
        visual_plan["type"] = "none"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic_instruction": topic_instruction,
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

    slug_source = topic_instruction if TOPIC else str(research.get("strongest_signal") or "autonomous-market-opportunity")
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in slug_source).strip("-")[:80] or "market-opportunity"
    path = OUTPUT_DIR / f"{safe_name}-multi-agent.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "model": MODEL,
        "topic_instruction": topic_instruction,
        "report": str(path),
        "quality_score": draft.get("quality_score"),
        "opportunity_score": research.get("opportunity_score"),
        "strongest_signal": research.get("strongest_signal"),
        "visual_requested": bool(visual_plan.get("use_visual")),
        "visual_type": visual_plan.get("type"),
        "strategy_memory_samples": strategy_memory.get("sample_size", 0),
        "gemini_requests_used": 1,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
