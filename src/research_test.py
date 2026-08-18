import json
import os
import sys
from pathlib import Path

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
TOPIC = os.getenv("TOPIC", "Bitcoin market overview")

SYSTEM = """You are the research agent for a Binance Square crypto creator.
Produce a research brief, not a trading instruction.
Use only information supplied in the prompt or general knowledge available to the model.
Do not invent live prices, statistics, breaking news, partnerships, or dates.
Clearly label anything that would require live verification.
Return valid JSON with keys: topic, summary, verified_style_facts, live_data_to_verify, possible_angles, risks, opportunity_score.
The opportunity_score must be an integer from 0 to 100 and represents content value, not investment potential."""


def main() -> int:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not configured.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM,
        input=f"Research the following possible Binance Square content topic: {TOPIC}",
    )

    text = response.output_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {
            "topic": TOPIC,
            "summary": text,
            "verified_style_facts": [],
            "live_data_to_verify": ["Model output was not valid JSON; human review required."],
            "possible_angles": [],
            "risks": ["Do not publish without review."],
            "opportunity_score": 0,
        }

    out = Path("data/reports")
    out.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c.lower() if c.isalnum() else "-" for c in TOPIC).strip("-")[:80]
    path = out / f"{safe_name or 'research'}-report.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Research report written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
