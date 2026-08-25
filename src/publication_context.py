"""Lock the production-cycle identity selected by Creator Brain.

This prevents the asset, editorial lane and engagement experiment from drifting
between Creator Brain, drafting, gating and publication.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/publication_context.json"


def load(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        return {}
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def clean_symbol(value: object) -> str:
    return str(value or "").upper().replace("USDT", "").strip()


def main() -> int:
    brain = load("data/live/creator_brain_decision.json")
    preflight = load("data/live/editorial_preflight.json")
    engagement = preflight.get("engagement_strategy") or {}
    experiment = engagement.get("experiment") or {}
    selected = preflight.get("selected_opportunity") or {}

    brain_symbol = clean_symbol(brain.get("symbol"))
    preflight_symbol = clean_symbol(selected.get("symbol"))
    locked_symbol = preflight_symbol or brain_symbol

    if preflight_symbol and brain_symbol and preflight_symbol != brain_symbol:
        # Preflight remains authoritative for the asset, as documented in Creator Brain.
        brain_alignment = "brain_refined_to_preflight"
    else:
        brain_alignment = "aligned"

    context = {
        "version": 1,
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "symbol": locked_symbol,
        "symbol_usdt": f"{locked_symbol}USDT" if locked_symbol else "",
        "category": str(selected.get("category") or "market_opportunity"),
        "opportunity_score": float(selected.get("adjusted_score") or selected.get("raw_score") or 0),
        "reason": str(selected.get("reason") or brain.get("reason") or ""),
        "instruction": str(selected.get("instruction") or ""),
        "editorial_format": str(brain.get("editorial_format") or experiment.get("format") or "CHOICE"),
        "conversation_goal": str(brain.get("conversation_goal") or "reply"),
        "experiment_id": str(engagement.get("experiment_id") or ""),
        "experiment_format": str(experiment.get("format") or brain.get("editorial_format") or ""),
        "market_phase": str(brain.get("market_phase") or "UNKNOWN"),
        "visual_decision": brain.get("visual_decision") or {},
        "brain_alignment": brain_alignment,
        "source": "creator_brain + editorial_preflight",
        "guardrail": "Drafts may refine wording and angle, but must not silently change the locked asset or experiment.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(context, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
