"""Merge Creator 7.2 learning into the existing strategy memory contract.

The existing creator already consumes analytics/strategy_memory.json. This bridge
keeps that interface stable while exposing the new outcome-learning preferences
and diagnoses to future content decisions.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEARNED = ROOT / "analytics/creator_7_2_strategy.json"
MEMORY = ROOT / "analytics/strategy_memory.json"


def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main():
    learned = load(LEARNED)
    memory = load(MEMORY)
    if not learned:
        print(json.dumps({"status": "NO_7_2_DATA", "message": "No Creator 7.2 strategy exists yet."}))
        return

    memory["creator_7_2"] = {
        "version": learned.get("version", "7.2"),
        "generated_at": learned.get("generated_at"),
        "learning_status": learned.get("learning_status"),
        "sample_size": learned.get("sample_size", 0),
        "wins": learned.get("wins", 0),
        "losses": learned.get("losses", 0),
        "mixed": learned.get("mixed", 0),
        "preference_changes": learned.get("preference_changes", []),
        "next_strategy": learned.get("next_strategy", {}),
        "revenue": learned.get("revenue", {}),
    }
    memory["learning_overlay"] = (
        "Creator 7.2 outcome learning is authoritative for repeated performance preferences. "
        "Use it as a strategy signal, never as permission to violate factual accuracy, originality, "
        "or anti-manipulation rules. Revenue fields are usable only when explicitly verified."
    )
    memory["generated_at"] = datetime.now(timezone.utc).isoformat()
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "version": "7.2", "memory": str(MEMORY), "sample_size": learned.get("sample_size", 0), "wins": learned.get("wins", 0), "losses": learned.get("losses", 0)}, ensure_ascii=False))


if __name__ == "__main__": main()
