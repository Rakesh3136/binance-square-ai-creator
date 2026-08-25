from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data/live/editorial_preflight.json"
INTELLIGENCE = ROOT / "data/live/creator_intelligence_2.json"


def main() -> None:
    if not PREFLIGHT.exists():
        raise SystemExit("Creator rework: editorial preflight is missing")

    data = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    intelligence = {}
    if INTELLIGENCE.exists():
        try:
            intelligence = json.loads(INTELLIGENCE.read_text(encoding="utf-8"))
        except Exception:
            intelligence = {}

    reasons = intelligence.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    reason_text = ", ".join(str(x) for x in reasons if str(x).strip()) or "the draft did not meet the creator standard"

    selected = data.get("selected_opportunity") or {}
    if not isinstance(selected, dict):
        selected = {}

    base = str(selected.get("instruction") or "Create the strongest evidence-based opportunity.").strip()
    selected["instruction"] = (
        base
        + "\n\nCREATOR INTELLIGENCE 2.0 REWORK: The previous draft was rejected for: "
        + reason_text
        + ". Rewrite from scratch. Do not reuse its hook, opening cadence, paragraph structure,"
          " question, or filler. Keep only verified facts. Make the thesis clearer, the voice"
          " more human, the angle more distinctive, and the final question specific enough to"
          " invite a real opinion. Never invent metrics, sources, prices, or claims."
    )
    data["selected_opportunity"] = selected
    data["run_ai"] = True
    data["reason"] = "creator_intelligence_rework"
    PREFLIGHT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "REWORK_REQUESTED", "reasons": reasons}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
