"""Bounded recovery loop for autonomous publication.

A hard editorial rejection should trigger one fresh regeneration/repair attempt,
not terminate the creator cycle. This module intentionally keeps the final elite
judge and production gates authoritative; it never bypasses them.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data/reports"
JUDGE = ROOT / "data/live/elite_prepublication_judge.json"


def run(name: str, env: dict[str, str]) -> None:
    print(f"[recovery] running {name}")
    p = subprocess.run([sys.executable, str(ROOT / "src" / name)], env=env)
    if p.returncode:
        raise SystemExit(p.returncode)


def latest_report() -> Path | None:
    xs = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return xs[0] if xs else None


def main() -> int:
    if not JUDGE.exists():
        print("[recovery] no elite judge result; refusing recovery")
        return 2
    try:
        judge = json.loads(JUDGE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[recovery] invalid judge JSON: {exc}")
        return 2

    failures = judge.get("failures") or []
    if not failures:
        print("[recovery] elite judge already passed; nothing to recover")
        return 0

    original = Path(os.environ.get("DRAFT_PATH", ""))
    if not original.exists():
        print(f"[recovery] original draft missing: {original}")
        return 2

    env = os.environ.copy()
    # Force a fresh generation path. safe_creator_runner itself handles Gemini
    # quota/error fallback and never invents unverified market facts.
    env["AUTONOMOUS_RECOVERY"] = "1"

    try:
        run("candidate_generation_4.py", env)
        run("safe_creator_runner.py", env)
        run("normalize_draft.py", env)
        run("technical_enricher.py", env)

        fresh = latest_report()
        if fresh is None:
            print("[recovery] no fresh report was produced")
            return 2

        # Local fallback may regenerate directly into the same report path.
        # Do not copy a file onto itself.
        fresh_resolved = fresh.resolve()
        original_resolved = original.resolve()
        if fresh_resolved != original_resolved:
            shutil.copy2(fresh_resolved, original_resolved)
            print(f"[recovery] promoted fresh report {fresh_resolved} -> {original_resolved}")
        else:
            print(f"[recovery] fresh report already is the authoritative draft: {original_resolved}")

        env["DRAFT_PATH"] = str(original_resolved)

        # Re-run the same deterministic editorial repair chain used by the main
        # pipeline, then run the authoritative elite judge again.
        run("candidate_script_scorer_4.py", env)
        run("human_editor.py", env)
        run("news_headline_integrity_repair.py", env)
        run("hook_diversity_rewriter.py", env)
        run("mechanism_value_rewriter.py", env)
        run("elite_prepublication_judge.py", env)
    except SystemExit as exc:
        print(f"[recovery] recovery command failed with code {exc.code}")
        return int(exc.code or 1)

    try:
        final = json.loads(JUDGE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[recovery] final judge JSON invalid: {exc}")
        return 2

    remaining = final.get("failures") or []
    print(json.dumps({
        "recovery": "completed",
        "original_failures": failures,
        "remaining_failures": remaining,
        "publish": final.get("publish") is True and not remaining,
        "draft_path": str(original),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
