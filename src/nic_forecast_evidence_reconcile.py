"""Reconcile forecast evidence after a concurrent main-branch update.

The source commit is the local evidence commit created earlier in the workflow.
This module intentionally keeps immutable source rows and de-duplicates by ID;
derived metrics are rebuilt by the workflow after reconciliation.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
LEDGER_IDENTITIES: dict[str, Callable[[dict[str, Any]], str]] = {
    "data/intelligence/nic_forecast_truth_ledger.jsonl": lambda row: str(row.get("forecast_id") or ""),
    "data/intelligence/nic_forecast_outcome_events.jsonl": lambda row: str(row.get("event_id") or row.get("forecast_id") or ""),
    "data/intelligence/nic_forecast_prospective_cohort.jsonl": lambda row: str(row.get("forecast_id") or ""),
    "data/intelligence/nic_forecast_prospective_outcome_events.jsonl": lambda row: str(row.get("event_id") or row.get("forecast_id") or ""),
    "data/intelligence/nic_regime_history.jsonl": lambda row: "|".join(str(row.get(key) or "") for key in ("timestamp", "symbol", "regime")),
}
REPORTS_TO_RESTORE = (
    "data/intelligence/nic_forecast_laboratory_report.json",
    "data/live/nic_forecast_laboratory.json",
)


def parse_jsonl(content: str, source_name: str = "JSONL") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {source_name}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Expected an object in {source_name}:{line_number}")
        rows.append(row)
    return rows


def merge_rows(
    current: Iterable[dict[str, Any]],
    incoming: Iterable[dict[str, Any]],
    identity: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    merged = list(current)
    seen = {identity(row) for row in merged if identity(row)}
    for row in incoming:
        key = identity(row)
        if key and key not in seen:
            merged.append(row)
            seen.add(key)
    return merged


def render_jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n" for row in rows)


def committed_file(commit: str, path: str) -> str:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], text=True, encoding="utf-8")


def reconcile(source_commit: str, root: Path = ROOT) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relative_path, identity in LEDGER_IDENTITIES.items():
        target = root / relative_path
        current = parse_jsonl(target.read_text(encoding="utf-8"), relative_path) if target.exists() else []
        incoming = parse_jsonl(committed_file(source_commit, relative_path), f"{source_commit}:{relative_path}")
        merged = merge_rows(current, incoming, identity)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_jsonl(merged), encoding="utf-8")
        counts[relative_path] = len(merged)

    for relative_path in REPORTS_TO_RESTORE:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(committed_file(source_commit, relative_path), encoding="utf-8")

    report_path = root / "data/intelligence/nic_forecast_laboratory_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    truth_path = root / "data/intelligence/nic_forecast_truth_ledger.jsonl"
    report["persisted_snapshot_count"] = sum(
        1 for line in truth_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    source_commit = os.environ.get("NIC_EVIDENCE_COMMIT", "").strip()
    if not source_commit:
        raise SystemExit("NIC_EVIDENCE_COMMIT is required to reconcile evidence after a rebase conflict.")
    counts = reconcile(source_commit)
    print(json.dumps({"status": "RECONCILED", "source_commit": source_commit, "ledger_rows": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
