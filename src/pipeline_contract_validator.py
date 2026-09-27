"""Static pipeline contract validation for the autonomous creator."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-market-creator.yml"

REQUIRED_ORDER = [
    "src/capital_flow_intelligence.py",
    "src/nic_prediction_engine.py",
    "src/nic_prediction_contract_validator.py",
    "src/signal_first_router.py",
    "src/safe_creator_runner.py",
    "src/candidate_script_scorer_4.py",
    "src/resolve_publish_draft.py",
    "src/human_editor.py",
    "src/elite_prepublication_gate.py",
    "src/content_integrity_gate_4.py",
    "src/production_manager.py",
    "src/publication_payload_builder.py",
    "src/write_to_earn_eligibility_gate.py",
    "src/write_to_earn_master.py",
    "src/binance_square_publisher.py",
]

SCRIPT_RE = re.compile(r"(?<![A-Za-z0-9_./-])python(?:3(?:\\.\\d+)?)?\\s+(src/[A-Za-z0-9_./-]+\\.py)(?![A-Za-z0-9_./-])")


def _mask_non_execution_regions(text: str) -> str:
    text = re.sub(r"PYTHONPATH=src\\s+python\\s+-c\\s+\".*?\"", lambda m: " " * len(m.group(0)), text, flags=re.DOTALL)
    return "".join("" if line.lstrip().startswith("#") else line for line in text.splitlines(keepends=True))


def referenced_scripts(text: str) -> list[str]:
    masked = _mask_non_execution_regions(text)
    seen: list[str] = []
    for match in SCRIPT_RE.finditer(masked):
        script = match.group(1)
        if script not in seen:
            seen.append(script)
    return seen


def execution_positions(text: str) -> dict[str, int]:
    masked = _mask_non_execution_regions(text)
    positions: dict[str, int] = {}
    for match in SCRIPT_RE.finditer(masked):
        positions.setdefault(match.group(1), match.start(1))
    for script in REQUIRED_ORDER:
        if script in positions:
            continue
        line_re = re.compile(rf"(?m)^\\s*python(?:3(?:\\.\\d+)?)?\\s+{re.escape(script)}(?:\\s*(?:#.*)?)?$")
        m = line_re.search(masked)
        if m:
            positions[script] = m.start()
    return positions


def tracked_files() -> set[str]:
    try:
        return set(subprocess.run(["git", "ls-files"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines())
    except Exception:
        return set()


def script_exists(path: str, tracked: set[str]) -> bool:
    return (ROOT / path).is_file() or path in tracked


def main() -> int:
    if not WORKFLOW.is_file():
        print(f"ERROR: workflow missing: {WORKFLOW}", file=sys.stderr)
        return 2
    text = WORKFLOW.read_text(encoding="utf-8")
    scripts = referenced_scripts(text)
    tracked = tracked_files()
    missing = [p for p in scripts if p != "src/creator_diagnostics.py" and not script_exists(p, tracked)]
    if missing:
        print("ERROR: workflow references missing Python files:", file=sys.stderr)
        for p in missing:
            print(f" - {p}", file=sys.stderr)
        return 2

    positions = execution_positions(text)
    absent = [p for p in REQUIRED_ORDER if p not in positions]
    if absent:
        print("ERROR: critical pipeline stages missing:", file=sys.stderr)
        for p in absent:
            print(f" - {p}", file=sys.stderr)
        return 2

    out_of_order = [(left, right) for left, right in zip(REQUIRED_ORDER, REQUIRED_ORDER[1:]) if positions[left] >= positions[right]]
    if out_of_order:
        print("ERROR: critical pipeline order is broken:", file=sys.stderr)
        for left, right in out_of_order:
            print(f" - {left} must precede {right}", file=sys.stderr)
        return 2

    if "DRAFT_PATH=$(python src/resolve_publish_draft.py)" not in text:
        print("ERROR: deterministic draft resolver is not wired into the editor stage", file=sys.stderr)
        return 2

    publish_marker = "Extract publication and submit to Binance Square"
    marker_index = text.find(publish_marker)
    if marker_index < 0:
        print("ERROR: publication stage marker is missing", file=sys.stderr)
        return 2
    publish_block = text[marker_index:]
    publisher_line = "python src/binance_square_publisher.py"
    if publisher_line not in publish_block:
        print("ERROR: Binance Square publisher is not wired into the publication stage", file=sys.stderr)
        return 2

    # Publication truth is intentionally collected before content generation so the
    # current cycle can learn from prior posts. The publisher itself writes the
    # authoritative current-run publication_result.json. Do not require the prior-
    # publication verifier or call tracker to appear after the publisher: that was a
    # false contract and caused valid runs to fail at the early integrity check.
    print(f"PIPELINE_CONTRACT_OK referenced_scripts={len(scripts)} critical_stages={len(REQUIRED_ORDER)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
