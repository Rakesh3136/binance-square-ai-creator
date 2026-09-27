"""Minimal durable pipeline state writer used by the autonomous orchestrator."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/pipeline_state.json"

def main() -> int:
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": os.getenv("GITHUB_RUN_NUMBER", ""),
        "sha": os.getenv("GITHUB_SHA", ""),
        "workflow": os.getenv("GITHUB_WORKFLOW", ""),
        "status": "RECORDED",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
