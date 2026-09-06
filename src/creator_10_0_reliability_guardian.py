#!/usr/bin/env python3
"""Creator 10.0 — bounded reliability and self-healing guardian.

This layer observes recent GitHub Actions failures, classifies them, performs
strict artifact sanity checks, and allows at most one safe failed-job rerun per
run. It never bypasses publication/quality gates and never fabricates data.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "analytics/creator_10_0_recovery_state.json"
REPORT = ROOT / "data/intelligence/creator_10_0_report.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "Rakesh3136/binance-square-ai-creator")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_RUNS = 20
MAX_RETRIES_PER_RUN = 1
MAX_RETRIES_PER_EXECUTION = 2

WATCH = {
    "Binance Square AI Creator 7.0",
    "Binance Square AI Creator 9.0",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def api(path: str) -> Any:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "binance-square-creator-10-0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def classify(step_names: list[str]) -> str:
    text = " ".join(step_names).lower()
    if "permission" in text or "auth" in text or "secret" in text:
        return "AUTH_OR_PERMISSION"
    if "validate tradingview" in text or "validation" in text:
        return "VALIDATION"
    if any(x in text for x in ("install", "dependency", "pip")):
        return "DEPENDENCY"
    if any(x in text for x in ("timeout", "network", "download", "connection")):
        return "NETWORK_OR_TRANSIENT"
    if any(x in text for x in ("publish", "publisher", "binance square")):
        return "PUBLICATION"
    return "UNKNOWN"


def artifact_audit() -> dict[str, Any]:
    checks: dict[str, Any] = {}
    visual = ROOT / "data/live/visual.png"
    checks["visual_png"] = {"exists": visual.exists(), "nonempty": visual.exists() and visual.stat().st_size > 0}
    for rel in ("data/live/market_snapshot.json", "data/live/news_snapshot.json"):
        p = ROOT / rel
        ok = False
        if p.exists():
            try:
                json.loads(p.read_text(encoding="utf-8"))
                ok = True
            except (json.JSONDecodeError, OSError):
                ok = False
        checks[rel] = {"exists": p.exists(), "valid_json": ok}
    return checks


def run_compile_check() -> bool:
    result = subprocess.run(
        ["python", "-m", "compileall", "-q", "src"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0


def rerun_failed(run_id: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "POST", f"repos/{REPO}/actions/runs/{run_id}/rerun-failed-jobs"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "RERUN_FAILED_JOBS_REQUESTED"
        return False, result.stderr.strip()[-500:]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def main() -> int:
    state = load_json(STATE, {"version": "10.0", "runs": {}, "last_run": None})
    state.setdefault("runs", {})
    events: list[dict[str, Any]] = []
    retries = 0

    if not TOKEN:
        report = {"version": "10.0", "status": "BLOCKED_NO_GITHUB_TOKEN", "generated_at": now()}
        save_json(REPORT, report)
        return 0

    try:
        runs = api("actions/runs?per_page=30").get("workflow_runs", [])
    except (urllib.error.URLError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        report = {"version": "10.0", "status": "OBSERVATION_ERROR", "error": str(exc), "generated_at": now()}
        save_json(REPORT, report)
        return 0

    for run in runs[:MAX_RUNS]:
        name = run.get("name", "")
        status = run.get("status")
        conclusion = run.get("conclusion")
        run_id = int(run.get("id", 0) or 0)
        if name not in WATCH or status != "completed" or conclusion != "failure" or not run_id:
            continue

        key = str(run_id)
        record = state["runs"].setdefault(key, {"retry_count": 0})
        try:
            jobs = api(f"actions/runs/{run_id}/jobs?per_page=100").get("jobs", [])
        except (urllib.error.URLError, OSError, RuntimeError, json.JSONDecodeError) as exc:
            events.append({"run_id": run_id, "workflow": name, "action": "INSPECT_FAILED", "error": str(exc)})
            continue

        failed_steps: list[str] = []
        for job in jobs:
            for step in job.get("steps", []) or []:
                if step.get("conclusion") == "failure":
                    failed_steps.append(step.get("name", "unknown step"))
        category = classify(failed_steps)
        audit = artifact_audit()
        retry_allowed = record.get("retry_count", 0) < MAX_RETRIES_PER_RUN and retries < MAX_RETRIES_PER_EXECUTION
        # Authentication/permission failures and publication failures are never
        # automatically retried. Validation is retried at most once, but never
        # bypassed. A second failure is escalated instead of looping.
        safe_category = category in {"VALIDATION", "DEPENDENCY", "NETWORK_OR_TRANSIENT", "UNKNOWN"}
        action = "NO_RETRY"
        detail = ""
        if retry_allowed and safe_category:
            ok, detail = rerun_failed(run_id)
            if ok:
                record["retry_count"] = int(record.get("retry_count", 0)) + 1
                record["last_action"] = "RERUN_FAILED_JOBS_REQUESTED"
                record["last_action_at"] = now()
                retries += 1
                action = "BOUNDED_RETRY"
            else:
                action = "RETRY_REQUEST_FAILED"
        elif record.get("retry_count", 0) >= MAX_RETRIES_PER_RUN:
            action = "ESCALATE_HUMAN_REVIEW"
            detail = "Retry budget exhausted; production gates remain authoritative."
        elif category in {"AUTH_OR_PERMISSION", "PUBLICATION"}:
            action = "BLOCKED_HUMAN_REVIEW"
            detail = "Potential credential/permission/publication failure; no automatic retry."

        events.append({
            "run_id": run_id,
            "workflow": name,
            "failed_steps": failed_steps,
            "category": category,
            "artifact_audit": audit,
            "action": action,
            "detail": detail,
        })

    state["last_run"] = now()
    state["last_events"] = events
    save_json(STATE, state)

    compile_ok = run_compile_check()
    blocked = any(e["action"] in {"ESCALATE_HUMAN_REVIEW", "BLOCKED_HUMAN_REVIEW"} for e in events)
    retried = any(e["action"] == "BOUNDED_RETRY" for e in events)
    status = "ESCALATION_REQUIRED" if blocked else ("RECOVERY_REQUESTED" if retried else "HEALTHY_NO_RECOVERY_NEEDED")
    if not compile_ok:
        status = "CODE_HEALTH_FAILURE"

    report = {
        "version": "10.0",
        "generated_at": now(),
        "status": status,
        "compileall_src_ok": compile_ok,
        "events": events,
        "hard_constraints": [
            "never bypass quality or publication gates",
            "never fabricate market, performance, engagement, or revenue data",
            "at most one automatic retry per failed run",
            "authentication, permission, and publication failures require review",
            "verified revenue only counts when explicitly verified by source data",
        ],
    }
    save_json(REPORT, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
