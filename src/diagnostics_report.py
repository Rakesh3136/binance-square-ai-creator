"""Lightweight post-run diagnostics snapshot for the autonomous orchestrator."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/diagnostics_report.json"

def main() -> int:
    live = ROOT / "data/live"
    intelligence = ROOT / "data/intelligence"
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": os.getenv("GITHUB_RUN_NUMBER", ""),
        "sha": os.getenv("GITHUB_SHA", ""),
        "status": "RECORDED",
        "live_file_count": sum(1 for p in live.glob("*") if p.is_file()) if live.exists() else 0,
        "intelligence_file_count": sum(1 for p in intelligence.glob("*") if p.is_file()) if intelligence.exists() else 0,
        "required_runtime_files": {
            "pipeline_state": (ROOT / "src/pipeline_state.py").exists(),
            "diagnostics_report": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
