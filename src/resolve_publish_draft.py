"""Resolve the canonical draft report for the publication pipeline.

The creator generates draft reports under data/reports/*-multi-agent.json. This
module provides a deterministic, testable handoff so the workflow never depends
on fragile shell find/sort/mtime parsing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"


def valid_report(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(value, dict):
        return False
    draft = value.get("draft")
    if not isinstance(draft, dict):
        return False
    text = str(draft.get("post") or draft.get("text") or "").strip()
    if not text:
        return False
    selected = value.get("selected_editorial_lane") or value.get("selected_opportunity") or {}
    if not isinstance(selected, dict):
        selected = {}
    symbol = str(
        selected.get("symbol")
        or draft.get("symbol")
        or value.get("symbol")
        or ""
    ).strip()
    if not symbol:
        return False
    return True


def resolve() -> Path:
    candidates = [
        p
        for p in REPORTS.glob("*-multi-agent.json")
        if p.is_file() and valid_report(p)
    ]
    if not candidates:
        raise RuntimeError(
            "No valid *-multi-agent.json draft report found in data/reports"
        )

    # Prefer newest valid report; tie-break lexically for deterministic behavior.
    candidates.sort(key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True)
    return candidates[0]


def main() -> int:
    try:
        path = resolve()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if REPORTS.exists():
            files = sorted(
                (str(p.relative_to(ROOT)) for p in REPORTS.glob("*-multi-agent.json") if p.is_file()),
                reverse=True,
            )[:10]
            if files:
                print("Candidates:", ", ".join(files), file=sys.stderr)
        return 2

    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
