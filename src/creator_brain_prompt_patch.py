"""Runtime bridge: make Creator Brain + publication context authoritative for Gemini drafting."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/multi_agent_creator.py"
BRAIN = ROOT / "data/live/creator_brain_decision.json"
CONTEXT = ROOT / "data/live/publication_context.json"
MARKER = "CREATOR_BRAIN_5_1_RUNTIME_BRIDGE"


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main():
    text = TARGET.read_text(encoding="utf-8")
    brain = read_json(BRAIN)
    context = read_json(CONTEXT)
    if not brain or not context:
        raise RuntimeError("Creator Brain 5.1 or publication context missing")

    if MARKER in text:
        print({"status": "CREATOR_BRAIN_5_1_BRIDGE_ALREADY_PRESENT"})
        return

    bridge = """        brain_context = (
        "\\n\\nCREATOR_BRAIN_5_1_RUNTIME_BRIDGE:\\n"
        "AUTHORITATIVE CREATOR BRAIN DECISION:\\n" + json.dumps(brain, ensure_ascii=False, indent=2) +
        "\\nAUTHORITATIVE PUBLICATION CONTEXT:\\n" + json.dumps(context, ensure_ascii=False, indent=2) +
        "\\nRULE: frozen primary asset, story engine, editorial format and verified chart symbols are authoritative. The final output must be a finished Binance Square post, not instructions to another writer. Use exactly one specific question. Never invent a second asset, news fact, source, price, target, creator call or outcome.\\n"
    )
"""

    pattern = r"(\n\s*prompt\s*=\s*\(\s*\n)"
    text, count = re.subn(pattern, lambda _: "\n" + bridge + "\n", text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate Gemini prompt construction")

    needle = '"EDITORIAL LANE:\\n" + instruction'
    replacement = 'brain_context + "EDITORIAL LANE:\\n" + instruction'
    if needle not in text:
        raise RuntimeError("Could not locate editorial lane prompt anchor")
    text = text.replace(needle, replacement, 1)

    TARGET.write_text(text, encoding="utf-8")
    print({"status": "CREATOR_BRAIN_5_1_BRIDGE_APPLIED"})


if __name__ == "__main__":
    main()
