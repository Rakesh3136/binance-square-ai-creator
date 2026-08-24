"""Durable stage tracker for one autonomous Binance Square production run."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/live/pipeline_status.json")

STAGES = [
    "creator_benchmark", "intelligence", "scan", "select", "creator_brain",
    "ai_draft", "visual", "quality_gate", "publish", "verify", "record",
    "learn", "complete", "finalize",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    if not OUT.exists():
        return {"run_started_at": now(), "stages": {}}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"run_started_at": now(), "stages": {}}
    except Exception:
        return {"run_started_at": now(), "stages": {}}


def save(data: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_run(reason="New autonomous production cycle") -> dict:
    data = {
        "run_started_at": now(),
        "last_updated_at": now(),
        "current_stage": "start",
        "last_successful_stage": None,
        "blocked_at": None,
        "stages": {},
        "reason": reason,
    }
    save(data)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def set_stage(stage: str, status: str, reason: str = "", **details) -> dict:
    if stage not in STAGES:
        raise SystemExit(f"Unknown pipeline stage: {stage}")
    data = load()
    data.setdefault("stages", {})
    data["last_updated_at"] = now()
    data["current_stage"] = stage
    data["stages"][stage] = {"status": status, "updated_at": now(), "reason": reason, **details}
    if status == "success":
        data["last_successful_stage"] = stage
    if status in {"failed", "blocked"}:
        data["blocked_at"] = stage
    if stage == "finalize":
        data["run_finished_at"] = now()
    save(data)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def verify_publish() -> int:
    result_path = Path("/tmp/publish-result.txt")
    if not result_path.exists():
        set_stage("verify", "failed", "publish result file missing")
        return 1
    result = result_path.read_text(encoding="utf-8", errors="replace")
    post_id = re.search(r"ID:\s*(\S+)", result)
    link = next((line.split("Link:", 1)[1].strip() for line in result.splitlines() if line.startswith("Link:")), None)
    if not post_id or not link:
        set_stage("verify", "failed", "publisher did not return a Binance post ID and link", result_tail=result[-1200:])
        return 1
    set_stage("verify", "success", "Binance publisher returned post ID and link", post_id=post_id.group(1), link=link)
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "reset":
        reset_run(" ".join(sys.argv[2:]) or "New autonomous production cycle")
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "verify-publish":
        return verify_publish()
    if len(sys.argv) < 3:
        raise SystemExit("usage: pipeline_stage.py <stage> <status> [reason] | reset [reason]")
    stage, status = sys.argv[1], sys.argv[2]
    reason = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
    set_stage(stage, status, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
