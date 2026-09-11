"""Bridge a verified prediction outcome into the existing content-selection contract.

The proof artifact is created before content selection. This bridge does not
publish and never creates a proof opportunity unless a terminal WIN exists.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "data/live/public_prediction_proof.json"
PREFLIGHT = ROOT / "data/live/editorial_preflight.json"
DIRECTOR = ROOT / "data/live/content_director_brief.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> int:
    proof = load(PROOF)
    if proof.get("status") != "VERIFIED_WIN_AVAILABLE" or not proof.get("publishable"):
        print(json.dumps({"status": "NO_PROOF_PRIORITY", "reason": "No verified WIN is available."}))
        return 0

    preflight = load(PREFLIGHT)
    director = load(DIRECTOR)
    symbol = str(proof.get("symbol") or "").upper()
    symbol_usdt = symbol if symbol.endswith("USDT") else symbol + "USDT"
    selected = {
        "category": "creator_signal_outcome",
        "symbol": symbol_usdt,
        "reason": "Verified prior prediction outcome is available for transparent public proof.",
        "score": 100.0,
        "lane": "accountability",
        "proof_status": proof.get("status"),
        "proof_type": proof.get("proof_type"),
        "call_id": proof.get("call_id"),
        "post_id": proof.get("post_id"),
        "direction": proof.get("direction"),
        "reference_price": proof.get("reference_price"),
        "target": proof.get("target"),
        "evaluated_at": proof.get("evaluated_at"),
        "original_publication_found": bool(proof.get("original_publication_found")),
        "content_brief": proof.get("content_brief"),
        "next_hook": proof.get("next_hook"),
    }

    brief = director if director else {}
    brief["run_ai"] = True
    brief["reason"] = "verified_prediction_proof_priority"
    brief["authoritative_selection"] = selected
    brief["primary_story"] = {
        "symbol": symbol,
        "lane": "creator_signal_outcome",
        "score": 100.0,
        "chart_symbols": [symbol] if symbol else [],
    }
    brief["recommended_format"] = "CALL OUTCOME / ACCOUNTABILITY"
    brief["narrative_engine"] = "call_result_next_test"
    brief.setdefault("interaction_plan", {})["primary_goal"] = "transparent proof followed by the next evidence-backed setup"
    brief["proof_priority"] = proof
    DIRECTOR.parent.mkdir(parents=True, exist_ok=True)
    DIRECTOR.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    preflight["selected_opportunity"] = selected
    preflight["content_director_4"] = brief
    PREFLIGHT.parent.mkdir(parents=True, exist_ok=True)
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"status": "PROOF_PRIORITY_SET", "selected": selected}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
