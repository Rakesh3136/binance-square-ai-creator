#!/usr/bin/env python3
"""Creator 10.1 — safe root-cause diagnosis and repair planner.

10.1 does not blindly rewrite production code. It fingerprints recurring
failures, verifies repository health, and creates a narrowly-scoped repair
plan. Automatic code changes are limited to an allow-list of deterministic
maintenance files; production quality gates remain authoritative.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analytics/creator_10_0_recovery_state.json"
STATE = ROOT / "analytics/creator_10_1_repair_state.json"
REPORT = ROOT / "data/intelligence/creator_10_1_report.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fingerprint(event: dict[str, Any]) -> str:
    raw = json.dumps({
        "workflow": event.get("workflow"),
        "failed_steps": event.get("failed_steps", []),
        "category": event.get("category"),
    }, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def compile_ok() -> bool:
    p = subprocess.run(["python", "-m", "compileall", "-q", "src"], cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode == 0


def main() -> int:
    recovery = load(INPUT, {"runs": {}})
    state = load(STATE, {"version": "10.1", "fingerprints": {}})
    state.setdefault("fingerprints", {})

    events = recovery.get("last_events", [])
    plans = []
    for event in events:
        fp = fingerprint(event)
        rec = state["fingerprints"].setdefault(fp, {"occurrences": 0, "repair_attempts": 0})
        rec["occurrences"] += 1
        category = event.get("category", "UNKNOWN")
        steps = event.get("failed_steps", [])
        repeated = rec["occurrences"] >= 2
        plan = {
            "fingerprint": fp,
            "category": category,
            "failed_steps": steps,
            "repeated": repeated,
            "repair_mode": "DIAGNOSE_ONLY",
            "reason": "No deterministic code defect has been proven from step metadata alone.",
        }
        if repeated:
            plan["repair_mode"] = "REVIEW_REQUIRED"
            plan["reason"] = "Recurring failure fingerprint detected; inspect exact failing logs before changing code."
        if category in {"AUTH_OR_PERMISSION", "PUBLICATION"}:
            plan["repair_mode"] = "BLOCKED"
            plan["reason"] = "Security/production boundary; automated code repair is prohibited."
        plans.append(plan)

    # Explicitly test the codebase before declaring a repair candidate healthy.
    healthy = compile_ok()
    status = "NO_REPAIR_REQUIRED" if not plans else "REPAIR_DIAGNOSTICS_READY"
    if not healthy:
        status = "CODE_HEALTH_FAILURE"

    report = {
        "version": "10.1",
        "generated_at": now(),
        "status": status,
        "source": "creator_10_0_recovery_state",
        "compileall_src_ok": healthy,
        "repair_plans": plans,
        "policy": {
            "no_blind_rewrites": True,
            "no_quality_gate_bypass": True,
            "no_fake_market_or_revenue_data": True,
            "recurring_failures_require_evidence": True,
            "auth_permission_publication_repairs_blocked": True,
        },
    }
    state["last_run"] = now()
    state["last_status"] = status
    save(STATE, state)
    save(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
