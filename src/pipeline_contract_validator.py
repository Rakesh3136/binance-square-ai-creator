"""Static pipeline contract validation for the autonomous creator.

This catches wiring errors before a live market run: missing referenced scripts,
broken critical ordering, and a missing deterministic draft handoff.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-market-creator.yml"

REQUIRED_ORDER = [
    "src/capital_flow_intelligence.py",
    "src/nic_prediction_engine.py",
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


def referenced_scripts(text: str) -> list[str]:
    seen: list[str] = []
    for match in re.findall(r"python\s+(src/[A-Za-z0-9_./-]+\.py)\b", text):
        if match not in seen:
            seen.append(match)
    return seen


def main() -> int:
    if not WORKFLOW.exists():
        print(f"ERROR: workflow missing: {WORKFLOW}", file=sys.stderr)
        return 2

    text = WORKFLOW.read_text(encoding="utf-8")
    scripts = referenced_scripts(text)
    # creator_diagnostics.py is intentionally optional in the persistence hook.
    missing = [p for p in scripts if p != "src/creator_diagnostics.py" and not (ROOT / p).exists()]

    if missing:
        print("ERROR: workflow references missing Python files:", file=sys.stderr)
        for p in missing:
            print(f" - {p}", file=sys.stderr)
        return 2

    positions = {p: text.find(p) for p in REQUIRED_ORDER}
    absent = [p for p, pos in positions.items() if pos < 0]
    if absent:
        print("ERROR: critical pipeline stages missing:", file=sys.stderr)
        for p in absent:
            print(f" - {p}", file=sys.stderr)
        return 2

    out_of_order = [
        (left, right)
        for left, right in zip(REQUIRED_ORDER, REQUIRED_ORDER[1:])
        if positions[left] >= positions[right]
    ]
    if out_of_order:
        print("ERROR: critical pipeline order is broken:", file=sys.stderr)
        for left, right in out_of_order:
            print(f" - {left} must precede {right}", file=sys.stderr)
        return 2

    if "DRAFT_PATH=$(python src/resolve_publish_draft.py)" not in text:
        print("ERROR: deterministic draft resolver is not wired into the editor stage", file=sys.stderr)
        return 2

    publisher_line = "python src/binance_square_publisher.py"
    verifier_line = "python src/creator_20_0_publication_verifier.py"
    publish_block = text[text.find("Extract publication and submit to Binance Square"):]
    if publisher_line not in publish_block or verifier_line not in publish_block:
        print("ERROR: publication publisher/verifier pair is not wired", file=sys.stderr)
        return 2
    if publish_block.find(publisher_line) >= publish_block.find(verifier_line):
        print("ERROR: publication verifier must run after publisher", file=sys.stderr)
        return 2

    print(
        f"PIPELINE_CONTRACT_OK referenced_scripts={len(scripts)} "
        f"critical_stages={len(REQUIRED_ORDER)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
