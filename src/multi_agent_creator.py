import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from google import genai

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
TOPIC = os.getenv("TOPIC", "Bitcoin market overview")
OUTPUT_DIR = Path("data/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def call_agent(client: genai.Client, system: str, prompt: str, max_tokens: int = 5000) -> str:
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


RESEARCH_SYSTEM = """You are the Research Agent for an elite Binance Square creator.
Think rigorously and independently. Do not reveal hidden chain-of-thought; provide concise conclusions and evidence requirements instead.
Do not invent live prices, breaking news, statistics, partnerships, or sources.
Separate durable background knowledge from facts that require live verification.
Return JSON with: thesis, durable_facts, live_facts_to_verify, audience_questions, possible_angles, risks, opportunity_score.
Opportunity score is 0-100 for content value, not investment potential."""

CRITIC_SYSTEM = """You are the Skeptical Analyst and Fact-Caution Agent.
Challenge the research brief. Identify weak assumptions, missing evidence, misleading framing, and likely reader objections.
Do not invent replacement facts. Do not provide hidden chain-of-thought.
Return JSON with: strongest_angle, weak_points, required_checks, counterpoints, recommended_position, revised_opportunity_score."""

WRITER_SYSTEM = """You are the Senior Binance Square Editor.
Create an original, useful post from the research and critique.
The result must clearly distinguish facts, interpretation, and uncertainty.
Never guarantee profits, create fake urgency, impersonate sources, or encourage reckless trading.
Use a strong first line, short paragraphs, concrete insight, and a thoughtful closing question.
Return JSON with: title, post, hook, key_takeaway, discussion_question, hashtags, quality_score.
Quality score is 0-100 for editorial quality, not investment return."""


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    research_text = call_agent(
        client,
        RESEARCH_SYSTEM,
        f"Analyze this potential Binance Square topic:\n\n{TOPIC}\n\nFocus on what is useful to a crypto audience and explicitly list what would need live verification before publication.",
    )
    research = parse_json(research_text)

    critique_text = call_agent(
        client,
        CRITIC_SYSTEM,
        "Review this research brief and challenge it:\n\n" + json.dumps(research, ensure_ascii=False, indent=2),
    )
    critique = parse_json(critique_text)

    writer_text = call_agent(
        client,
        WRITER_SYSTEM,
        "Create the final draft using this research and critique. Do not invent missing live facts.\n\nRESEARCH:\n"
        + json.dumps(research, ensure_ascii=False, indent=2)
        + "\n\nCRITIQUE:\n"
        + json.dumps(critique, ensure_ascii=False, indent=2),
        max_tokens=6000,
    )
    draft = parse_json(writer_text)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "topic": TOPIC,
        "research": research,
        "critique": critique,
        "draft": draft,
        "status": "DRAFT_ONLY_NOT_PUBLISHED",
    }

    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in TOPIC).strip("-")[:80] or "research"
    path = OUTPUT_DIR / f"{safe_name}-multi-agent.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "model": MODEL,
        "topic": TOPIC,
        "report": str(path),
        "quality_score": draft.get("quality_score"),
        "opportunity_score": research.get("opportunity_score"),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
