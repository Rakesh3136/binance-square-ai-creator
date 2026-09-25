"""Regression checks for the workflow contract validator."""
from __future__ import annotations

from pipeline_contract_validator import REQUIRED_ORDER, execution_positions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "autonomous-market-creator.yml"


def main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    positions = execution_positions(text)
    missing = [stage for stage in REQUIRED_ORDER if stage not in positions]
    assert not missing, f"validator missed real workflow stages: {missing}"
    assert all(positions[a] < positions[b] for a, b in zip(REQUIRED_ORDER, REQUIRED_ORDER[1:])), "required stage order is broken"
    print(f"PIPELINE_CONTRACT_VALIDATOR_REGRESSION_OK stages={len(REQUIRED_ORDER)}")


if __name__ == "__main__":
    main()
