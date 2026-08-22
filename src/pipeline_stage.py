"""Durable stage tracker for one autonomous Binance Square production run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/live/pipeline_status.json")

STAGES = [
    "scan",
    "select",
    "ai_draft",
    "visual",
    "quality_gate",
    "publish",
    "verify",
    "record",
    "learn",
    "complete",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    if not OUT.exists():
        return {"run_started_at": now(), "stages": {}}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"run_started_at": now(), "stages": {}}


def save(data: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def set_stage(stage: str, status: str, reason: str = "", **details) -> dict:
    if stage not in STAGES:
        raise SystemExit(f"Unknown pipeline stage: {stage}")
    data = load()
    if "stages" not in data:
        data["stages"] = {}
    data["last_updated_at"] = now()
    data["current_stage"] = stage
    data["stages"][stage] = {
        "status": status,
        "updated_at": now(),
        "reason": reason,
        **details,
    }
    if status == "success":
        data["last_successful_stage"] = stage
    if status in {"failed", "blocked"}:
        data["blocked_at"] = stage
    save(data)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: pipeline_stage.py <stage> <status> [reason]")
    stage, status = sys.argv[1], sys.argv[2]
    reason = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    set_stage(stage, status, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
