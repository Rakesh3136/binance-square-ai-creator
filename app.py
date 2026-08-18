import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
OUTPUT_DIR = Path("data/reports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are the research brain of an autonomous Binance Square creator.

Your job is to produce a research brief, not a trading instruction.
Never invent live facts, prices, statistics, news, quotes, or sources.
Clearly separate verified facts, analysis, and unknowns.
Prefer primary sources and reputable financial/crypto sources.
Return valid JSON with keys: topic, why_now, verified_facts, analysis, uncertainties, content_angles, opportunity_score.
The opportunity_score is 0-100 and should reflect timeliness, audience interest, originality, usefulness, discussion potential, and evidence quality.
"""


def run(topic: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=(
            f"Prepare a research brief for this topic: {topic}\n"
            "Do not pretend you have live market data unless it is provided in the input. "
            "State clearly what must be verified externally before publication."
        ),
    )

    text = response.output_text.strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"raw_output": text}

    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result


if __name__ == "__main__":
    topic = os.getenv("TOPIC", "Bitcoin market overview")
    result = run(topic)
    filename = OUTPUT_DIR / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    filename.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
