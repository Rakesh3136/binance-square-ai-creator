"""Creator 6.6 authenticity + learned-style authority.

Runs after Creator 6.5 identity selection. It converts verified performance learning
into explicit writing constraints and adds a human-creator mode so the model does not
fall back to one reusable AI template. It never changes the selected asset without
evidence and never invents metrics.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREF = ROOT / "data/live/editorial_preflight.json"
IDENTITY = ROOT / "data/live/creator_identity_6.json"
FEEDBACK = ROOT / "data/intelligence/performance_feedback.json"
OUT = ROOT / "data/live/creator_identity_6_6.json"

VOICE_MODES = [
    "field_note", "analyst_take", "mini_case", "chart_lesson",
    "contrarian_read", "event_breakdown", "scenario_test", "postmortem"
]


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> None:
    pref = load(PREF)
    identity = load(IDENTITY)
    feedback = load(FEEDBACK)
    selected = dict(pref.get("selected_opportunity") or identity.get("selected") or {})

    rotation = identity.get("rotation") or {}
    recent_modes = rotation.get("recent_voice_modes") or []
    counts = Counter(str(x) for x in recent_modes)
    mode = min(VOICE_MODES, key=lambda x: (counts[x], VOICE_MODES.index(x)))

    learned = feedback.get("learned_preferences") or {}
    preferred_format = ((learned.get("format") or {}).get("prefer"))
    preferred_style = ((learned.get("style") or {}).get("prefer"))
    preferred_hook = ((learned.get("hook_type") or {}).get("prefer"))

    constraints = {
        "version": "6.6",
        "voice_mode": mode,
        "learned_preference_format": preferred_format,
        "learned_preference_style": preferred_style,
        "learned_preference_hook": preferred_hook,
        "rules": [
            "Be an original market commentator, not a rewritten news headline.",
            "Add one clear interpretation that follows from the evidence; do not merely restate numbers.",
            "Use natural sentence rhythm: mix short and medium sentences and avoid numbered-template cadence unless the format calls for it.",
            "Do not open with the same ticker-plus-percentage construction used in recent posts.",
            "Do not use generic filler such as 'What do you think?' or 'Stay tuned'.",
            "Do not manufacture personal trades, holdings, PnL, or experiences.",
            "Do not manufacture certainty, targets, whale activity, liquidation totals, or news impact.",
            "If the selected story is news, explain why it matters to the selected asset/market instead of copying the headline.",
            "If the selected story is technical, make the chart the evidence and explain the decision point.",
            "If the selected story is a mover, explain the unusual condition or risk rather than only announcing the percentage move.",
            "Use one concrete interaction question tied to the post's actual decision point.",
            "TradingView is the only chart source; the chart must match the selected asset/story.",
            "Never substitute BTC as a generic chart proxy."
        ]
    }

    instruction = (
        f"Creator 6.6 authenticity layer: use voice mode={mode}. "
        f"Learned preference signals are advisory only: format={preferred_format or 'explore'}, "
        f"style={preferred_style or 'explore'}, hook={preferred_hook or 'explore'}. "
        "Write like an original human market commentator: interpret the evidence, do not paraphrase the source. "
        "Vary sentence rhythm, opening construction, paragraph shape and CTA. "
        "Never invent personal experience or missing facts. Keep the selected opportunity and asset authoritative. "
        "TradingView only, with a chart matching the selected asset/story."
    )
    selected["instruction"] = instruction
    selected["authenticity_constraints"] = constraints
    pref["selected_opportunity"] = selected
    pref["content_director_instruction"] = instruction
    pref["creator_identity_6_6"] = {
        "version": "6.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "voice_mode": mode,
        "learned_preferences": {
            "format": preferred_format,
            "style": preferred_style,
            "hook": preferred_hook,
        },
        "constraints": constraints,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "version": "6.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected": selected,
        "voice_mode": mode,
        "learned_preferences": learned,
        "constraints": constraints,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    PREF.write_text(json.dumps(pref, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "version": "6.6",
        "voice_mode": mode,
        "selected_symbol": selected.get("symbol"),
        "selected_category": selected.get("category"),
        "tradingview_only": True,
        "authenticity_layer": True,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
