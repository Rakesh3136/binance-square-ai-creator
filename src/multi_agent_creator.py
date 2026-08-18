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


def load_live_context() -> dict:
    if not LIVE_SNAPSHOT.exists():
        return {}
    return json.loads(LIVE_SNAPSHOT.read_text(encoding="utf-8"))


RESEARCH_SYSTEM = """You are the Research Agent for an elite Binance Square creator.
Use the supplied live market snapshot as factual market input. Do not invent live prices, statistics, breaking news, partnerships, or sources.
Treat every supplied market number as an observation timestamped by its source. Separate observations from interpretation.
Find the most interesting content-worthy market signals and explain why an ordinary crypto reader should care.
Return JSON with: thesis, strongest_signal, market_observations, audience_questions, possible_angles, risks, live_verification_needed, opportunity_score.
Opportunity score is 0-100 for content value, not investment potential."""

CRITIC_SYSTEM = """You are the Skeptical Analyst and Fact-Caution Agent.
Challenge the research brief. Check whether the proposed angle follows from the supplied market observations.
Identify weak assumptions, misleading causal claims, overhyped wording, missing context, and what cannot be concluded from 24-hour ticker data alone.
Do not invent replacement facts. Do not reveal hidden chain-of-thought.
Return JSON with: strongest_angle, weak_points, missing_context, required_checks, counterpoints, safer_wording, revised_opportunity_score."""

WRITER_SYSTEM = """You are the Senior Binance Square Editor.
Create an original, useful post from the live market research and critique.
Only use numbers present in the supplied research context. Clearly distinguish observation from interpretation.
Never guarantee profits, create fake urgency, impersonate sources, coordinate manipulation, or encourage reckless trading.
Use a strong first line, short readable paragraphs, concrete insight, and a thoughtful closing question.
Return JSON with: title, post, hook, key_takeaway, discussion_question, hashtags, quality_score.
Quality score is 0-100 for editorial quality, not investment return."""


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)
    live_context = load_live_context()

    if not live_context and not TOPIC:
        raise RuntimeError("No live market snapshot and no TOPIC supplied")

    topic_instruction = TOPIC or "Choose the single strongest Binance Square content opportunity from the live market snapshot."
    research_text = call_agent(
        client,
        RESEARCH_SYSTEM,
        "Topic instruction:\n" + topic_instruction + "\n\nLIVE MARKET SNAPSHOT:\n" + json.dumps(live_context, ensure_ascii=False, indent=2),
    )
    research = parse_json(research_text)

    critique_text = call_agent(
        client,
        CRITIC_SYSTEM,
        "Review this research against the live market snapshot:\n\nRESEARCH:\n"
        + json.dumps(research, ensure_ascii=False, indent=2)
        + "\n\nLIVE SNAPSHOT:\n"
        + json.dumps(live_context, ensure_ascii=False, indent=2),
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
        + json.dumps(live_context, ensure_ascii=False, indent=2),
    )
    draft = parse_json(writer_text)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic_instruction": topic_instruction,
        "live_market_snapshot": live_context,
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
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
