"""Authoritative wrapper around the existing elite pre-publication judge.

The judge performs the substantive editorial checks. This module converts its
decision into a single hard publication gate and never rewrites content.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "data" / "live" / "elite_prepublication_judge.json"
OUT = ROOT / "data" / "live" / "elite_prepublication_gate.json"
REPORT = ROOT / "data" / "intelligence" / "elite_prepublication_gate_report.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    judge = load(JUDGE)

    # A judge result is valid only for the current draft. This prevents a
    # recovered draft from accidentally inheriting a PASS/BLOCK decision from
    # an earlier version of the same cycle.
    draft_raw = __import__("os").getenv("DRAFT_PATH", "").strip()
    stale_judge = False
    if draft_raw:
        draft_path = Path(draft_raw)
        try:
            stale_judge = (not JUDGE.exists()) or (JUDGE.stat().st_mtime + 0.5 < draft_path.stat().st_mtime)
        except OSError:
            stale_judge = True
    if stale_judge:
        result = {
            "version": "1.1-authoritative-wrapper",
            "generated_at": now,
            "status": "BLOCKED",
            "publish": False,
            "judge_version": judge.get("version"),
            "overall": judge.get("overall"),
            "failures": ["stale_or_missing_judge_for_current_draft"],
            "decision": "STOP_BEFORE_PRODUCTION",
            "policy": {
                "judge_is_authoritative": True,
                "no_content_rewrite": True,
                "no_gate_bypass": True,
                "fresh_judge_required": True,
            },
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    publish = judge.get("publish") is True
    failures = judge.get("failures") if isinstance(judge.get("failures"), list) else []
    result = {
        "version": "1.1-authoritative-wrapper",
        "generated_at": now,
        "status": "PASS" if publish else "BLOCKED",
        "publish": publish,
        "judge_version": judge.get("version"),
        "overall": judge.get("overall"),
        "failures": failures,
        "decision": "ALLOW_DOWNSTREAM_GATES" if publish else "STOP_BEFORE_PRODUCTION",
        "policy": {
            "judge_is_authoritative": True,
            "no_content_rewrite": True,
            "no_gate_bypass": True,
            "recovery_requires_a_fresh_eligible_run": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if publish else 1


if __name__ == "__main__":
    raise SystemExit(main())
