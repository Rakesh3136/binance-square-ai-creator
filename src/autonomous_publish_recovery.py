"""Bounded recovery loop for autonomous publication.

A hard editorial rejection triggers a fresh regeneration/repair attempt. The
recovery may perform one additional deterministic repetition repair if the first
repair still leaves a recent-sentence collision. The final elite judge and
production gates remain authoritative; recovery never bypasses them.
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


def read_judge() -> dict:
    try:
        return json.loads(JUDGE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    if not JUDGE.exists():
        print("[recovery] no elite judge result; refusing recovery")
        return 2
    judge = read_judge()
    failures = judge.get("failures") or []
    if not failures:
        print("[recovery] elite judge already passed; nothing to recover")
        return 0

    original = Path(os.environ.get("DRAFT_PATH", ""))
    if not original.exists():
        print(f"[recovery] original draft missing: {original}")
        return 2

    env = os.environ.copy()
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

        fresh_resolved = fresh.resolve()
        original_resolved = original.resolve()
        if fresh_resolved != original_resolved:
            shutil.copy2(fresh_resolved, original_resolved)
            print(f"[recovery] promoted fresh report {fresh_resolved} -> {original_resolved}")
        else:
            print(f"[recovery] fresh report already is the authoritative draft: {original_resolved}")

        env["DRAFT_PATH"] = str(original_resolved)
        run("candidate_script_scorer_4.py", env)
        run("human_editor.py", env)
        run("news_headline_integrity_repair.py", env)
        run("hook_diversity_rewriter.py", env)
        run("mechanism_value_rewriter.py", env)
        run("elite_prepublication_judge.py", env)

        # One bounded deterministic cleanup is allowed when the only remaining
        # hard blocker is recent-sentence repetition. This specifically handles
        # posts containing multiple repeated sentences in the same paragraph.
        final = read_judge()
        remaining = final.get("failures") or []
        if "repeats_recent_published_sentence" in remaining:
            print("[recovery] repetition remains; running one final deterministic sentence repair")
            run("hook_diversity_rewriter.py", env)
            run("elite_prepublication_judge.py", env)
    except SystemExit as exc:
        print(f"[recovery] recovery command failed with code {exc.code}")
        return int(exc.code or 1)

    final = read_judge()
    remaining = final.get("failures") or []
    publish = final.get("publish") is True and not remaining
    print(json.dumps({
        "recovery": "completed",
        "original_failures": failures,
        "remaining_failures": remaining,
        "publish": publish,
        "draft_path": str(original),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
