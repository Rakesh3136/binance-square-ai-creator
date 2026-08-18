import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from google import genai

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TOPIC = os.getenv("TOPIC", "")
OUTPUT_DIR = Path("data/reports")
LIVE_SNAPSHOT = Path("data/live/market_snapshot.json")
NEWS_SNAPSHOT = Path("data/live/news_snapshot.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def call_agent(client: genai.Client, system: str, prompt: str) -> str:
    interaction = client.interactions.create(
        model=MODEL,
        input=prompt,
        system_instruction=system,
    )
    text = (interaction.output_text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


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
    return {"raw": text}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


RESEARCH_SYSTEM = """You are the Research Agent for an elite Binance Square creator.
Use the supplied market snapshot and news-discovery snapshot.
Market numbers are observations from the supplied timestamped source.
RSS news items are discovery leads, NOT verified facts. Treat article summaries as leads and preserve source URLs.
Never invent live prices, statistics, breaking news, partnerships, or sources.
Find the strongest content-worthy story by combining market signal + credible news context + audience usefulness.
Separate facts, observations, inference, and unknowns.
Return JSON with: thesis, strongest_signal, market_observations, news_leads, source_urls, audience_questions, possible_angles, risks, live_verification_needed, opportunity_score.
Opportunity score is 0-100 for content value, not investment potential."""

CRITIC_SYSTEM = """You are the Skeptical Analyst, Fact-Caution Agent, and Source-Integrity Editor.
Challenge the research brief.
Check whether the proposed causal explanation is actually supported by the supplied market observations and news leads.
Treat RSS items as leads until verified; distinguish reporting from primary-source confirmation.
Identify weak assumptions, misleading causal claims, overhyped wording, missing context, stale items, and what cannot be concluded from the supplied data.
Do not invent replacement facts. Do not reveal hidden chain-of-thought.
Return JSON with: strongest_angle, weak_points, missing_context, source_verification_plan, required_checks, counterpoints, safer_wording, revised_opportunity_score."""

WRITER_SYSTEM = """You are the Senior Binance Square Editor.
Create an original, useful post from the supplied research and critique.
Do not copy or closely paraphrase source articles. Add a distinct explanatory angle.
Only use numbers and concrete claims present in the supplied research context and label unresolved items as unverified.
Clearly distinguish observation from interpretation.
Never guarantee profits, create fake urgency, impersonate sources, coordinate manipulation, or encourage reckless trading.
Use a strong first line, short readable paragraphs, concrete insight, and a thoughtful closing question.
Include source URLs when useful, but do not pretend a secondary article is a primary source.
Return JSON with: title, post, hook, key_takeaway, discussion_question, hashtags, source_links, publication_status, quality_score.
Quality score is 0-100 for editorial quality, not investment return."""


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)
    live_context = load_json(LIVE_SNAPSHOT)
    news_context = load_json(NEWS_SNAPSHOT)

    if not live_context and not news_context and not TOPIC:
        raise RuntimeError("No market/news context and no TOPIC supplied")

    topic_instruction = TOPIC or "Choose the single strongest Binance Square content opportunity from the live market and news-discovery snapshots."
    research_text = call_agent(
        client,
        RESEARCH_SYSTEM,
        "Topic instruction:\n" + topic_instruction
        + "\n\nLIVE MARKET SNAPSHOT:\n" + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS-DISCOVERY SNAPSHOT:\n" + json.dumps(news_context, ensure_ascii=False, indent=2),
    )
    research = parse_json(research_text)

    critique_text = call_agent(
        client,
        CRITIC_SYSTEM,
        "Review this research against the supplied market and news context:\n\nRESEARCH:\n"
        + json.dumps(research, ensure_ascii=False, indent=2)
        + "\n\nLIVE MARKET SNAPSHOT:\n"
        + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nNEWS-DISCOVERY SNAPSHOT:\n"
        + json.dumps(news_context, ensure_ascii=False, indent=2),
    )
    critique = parse_json(critique_text)

    writer_text = call_agent(
        client,
        WRITER_SYSTEM,
        "Create the final draft using this research and critique. Do not invent missing live facts.\n\nRESEARCH:\n"
        + json.dumps(research, ensure_ascii=False, indent=2)
        + "\n\nCRITIQUE:\n"
        + json.dumps(critique, ensure_ascii=False, indent=2)
        + "\n\nSOURCE MARKET SNAPSHOT:\n"
        + json.dumps(live_context, ensure_ascii=False, indent=2)
        + "\n\nSOURCE NEWS SNAPSHOT:\n"
        + json.dumps(news_context, ensure_ascii=False, indent=2),
    )
    draft = parse_json(writer_text)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic_instruction": topic_instruction,
        "live_market_snapshot": live_context,
        "news_discovery_snapshot": news_context,
        "research": research,
        "critique": critique,
        "draft": draft,
        "status": "DRAFT_ONLY_NOT_PUBLISHED",
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
        "news_leads_used": len(research.get("news_leads", [])) if isinstance(research.get("news_leads"), list) else 0,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
