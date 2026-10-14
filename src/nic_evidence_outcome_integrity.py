"""Fail-closed reconciliation of NIC forecast snapshots and terminal outcomes.

This validates evidence integrity only. VERIFIED never means the strategy is profitable
and this module never authorizes trading or publishing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INTEL = ROOT / "data/intelligence"
SNAPSHOTS = INTEL / "nic_forecast_prospective_cohort.jsonl"
OUTCOMES = INTEL / "nic_forecast_prospective_outcome_events.jsonl"
PROFITABILITY = INTEL / "nic_forecast_profitability.json"
OUTPUT = INTEL / "nic_evidence_outcome_integrity.json"


class EvidenceError(ValueError):
    """Evidence is malformed or internally contradictory."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes() if path.exists() else b"").hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"{path.name}:{line_number}: malformed JSON") from exc
        if not isinstance(row, dict):
            raise EvidenceError(f"{path.name}:{line_number}: each record must be an object")
        rows.append(row)
    return rows


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _has_source_provenance(snapshot: dict[str, Any]) -> bool:
    """Require canonical, reproducible source metadata; a URL alone is insufficient."""
    source = snapshot.get("source_provenance")
    if not isinstance(source, dict):
        return False
    required = ("provider", "endpoint", "instrument", "interval", "closed_candle_open_time",
                "closed_candle_as_of", "retrieved_at", "strategy_spec_sha256")
    if any(not isinstance(source.get(key), str) or not source[key].strip() for key in required):
        return False
    if not source["endpoint"].startswith("https://"):
        return False
    for key in ("closed_candle_open_time", "closed_candle_as_of", "retrieved_at"):
        if not _timestamp(source[key]):
            return False
    digest = source["strategy_spec_sha256"]
    return len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest.lower())


def source_evidence(snapshots: list[dict[str, Any]], outcomes: list[dict[str, Any]],
                    resolved_count: int, snapshot_sha256: str, outcomes_sha256: str) -> dict[str, Any]:
    return {
        "snapshot_ledger_sha256": snapshot_sha256,
        "outcome_ledger_sha256": outcomes_sha256,
        "snapshot_count": len(snapshots),
        "terminal_outcome_count": sum(row.get("event_type") == "FORECAST_RESOLVED" for row in outcomes),
        "resolved_forecast_count": resolved_count,
    }


def evaluate_evidence(
    snapshots: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    report: dict[str, Any] | None,
    snapshot_sha256: str,
    outcomes_sha256: str,
) -> dict[str, Any]:
    """Check immutable IDs, explicit terminal joins, provenance, and report-to-ledger equality."""
    errors: list[str] = []
    warnings: list[str] = []
    warning_counts: dict[str, int] = {}

    def add_warning(code: str, detail: str | None = None) -> None:
        warning_counts[code] = warning_counts.get(code, 0) + 1
        # Keep the report compact; counts preserve the full population.
        if len(warnings) < 25:
            warnings.append(f"{code}:{detail}" if detail else code)

    snapshot_by_id: dict[str, dict[str, Any]] = {}
    terminal_by_id: dict[str, dict[str, Any]] = {}

    for index, snapshot in enumerate(snapshots, 1):
        forecast_id = str(snapshot.get("forecast_id") or "").strip()
        if not forecast_id:
            errors.append(f"snapshot_record_{index}_missing_forecast_id")
            continue
        if forecast_id in snapshot_by_id:
            errors.append(f"duplicate_snapshot_forecast_id:{forecast_id}")
            continue
        snapshot_by_id[forecast_id] = snapshot
        if not _timestamp(snapshot.get("timestamp") or snapshot.get("created_at")):
            add_warning("snapshot_missing_valid_timestamp", forecast_id)
        if not _has_source_provenance(snapshot):
            add_warning("snapshot_missing_source_provenance", forecast_id)

    terminal_events = [row for row in outcomes if row.get("event_type") == "FORECAST_RESOLVED"]
    for index, event in enumerate(terminal_events, 1):
        forecast_id = str(event.get("forecast_id") or "").strip()
        if not forecast_id:
            errors.append(f"terminal_outcome_{index}_missing_forecast_id")
            continue
        if forecast_id in terminal_by_id:
            errors.append(f"duplicate_terminal_outcome_forecast_id:{forecast_id}")
            continue
        terminal_by_id[forecast_id] = event
        if forecast_id not in snapshot_by_id:
            errors.append(f"orphan_terminal_outcome:{forecast_id}")
        if _number(event.get("signed_return")) is None:
            errors.append(f"terminal_outcome_invalid_signed_return:{forecast_id}")
        if not _timestamp(event.get("resolved_at") or event.get("timestamp")):
            add_warning("terminal_outcome_missing_valid_timestamp", forecast_id)

    resolved_ids = sorted(set(snapshot_by_id) & set(terminal_by_id))
    actionable_ids: set[str] = set()
    for forecast_id in resolved_ids:
        snapshot = snapshot_by_id[forecast_id]
        event = terminal_by_id[forecast_id]
        side = str(snapshot.get("side") or event.get("side") or "").upper()
        decision = str(snapshot.get("decision") or "").upper()
        expected = {"BULLISH": "LONG_CANDIDATE", "BEARISH": "SHORT_CANDIDATE"}.get(side)
        if expected and decision == expected and _has_source_provenance(snapshot):
            actionable_ids.add(forecast_id)

    if not resolved_ids:
        add_warning("no_explicit_terminal_outcomes_joined_to_snapshots")

    actual_source = source_evidence(
        snapshots, outcomes, len(resolved_ids), snapshot_sha256, outcomes_sha256
    )
    if not isinstance(report, dict):
        add_warning("profitability_report_missing_or_invalid")
        report = {}
    evidence = report.get("source_evidence")
    if not isinstance(evidence, dict):
        add_warning("profitability_report_missing_source_evidence")
    else:
        for key, actual in actual_source.items():
            if evidence.get(key) != actual:
                errors.append(
                    f"report_source_evidence_mismatch:{key}:"
                    f"reported={evidence.get(key)!r}:actual={actual!r}"
                )
    if report:
        if report.get("resolved_forecast_count") != len(resolved_ids):
            errors.append(
                "report_resolved_forecast_count_mismatch:"
                f"reported={report.get('resolved_forecast_count')!r}:actual={len(resolved_ids)}"
            )
        if report.get("sample_count") != len(actionable_ids):
            errors.append(
                "report_actionable_sample_count_mismatch:"
                f"reported={report.get('sample_count')!r}:actual={len(actionable_ids)}"
            )

    if errors:
        status = "FAILED"
    elif warning_counts:
        status = "BLOCKED"
    else:
        status = "VERIFIED"

    return {
        "schema": "NIC-EVIDENCE-OUTCOME-INTEGRITY-1.1",
        "cohort_policy": "PROSPECTIVE_FROZEN_PROVENANCE_BACKED_ONLY",
        "status": status,
        "checked_at": datetime.now().astimezone().isoformat(),
        "mode": "READ_ONLY_EVIDENCE_AUDIT",
        "snapshot_count": len(snapshots),
        "terminal_outcome_count": len(terminal_events),
        "joined_resolved_forecast_count": len(resolved_ids),
        "joined_actionable_sample_count": len(actionable_ids),
        "source_evidence": actual_source,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "warning_counts": dict(sorted(warning_counts.items())),
        "warning_total_count": sum(warning_counts.values()),
        "profitability_status": str(report.get("status") or "NOT_PROVEN"),
        "profitability_proven": False,
        "trade_authorized": False,
        "publication_authorized": False,
        "interpretation": (
            "Evidence integrity passed; profitability still requires a separate cost-aware, "
            "chronological, non-overlapping held-out portfolio test."
            if status == "VERIFIED"
            else "Evidence is not eligible to support a profitability claim. Repair every error "
            "and warning, regenerate the report from the exact ledgers, and rerun this audit."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, default=SNAPSHOTS)
    parser.add_argument("--outcomes", type=Path, default=OUTCOMES)
    parser.add_argument("--report", type=Path, default=PROFITABILITY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    try:
        snapshots = read_jsonl(args.snapshots)
        outcomes = read_jsonl(args.outcomes)
        try:
            report_value = json.loads(args.report.read_text(encoding="utf-8"))
            report = report_value if isinstance(report_value, dict) else None
        except (OSError, json.JSONDecodeError):
            report = None
        result = evaluate_evidence(
            snapshots, outcomes, report, sha256_file(args.snapshots), sha256_file(args.outcomes)
        )
    except (OSError, EvidenceError) as exc:
        result = {
            "schema": "NIC-EVIDENCE-OUTCOME-INTEGRITY-1.0",
            "status": "FAILED",
            "mode": "READ_ONLY_EVIDENCE_AUDIT",
            "errors": [str(exc)],
            "warnings": [],
            "profitability_status": "NOT_PROVEN",
            "profitability_proven": False,
            "trade_authorized": False,
            "publication_authorized": False,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "snapshots": result.get("snapshot_count", 0),
        "terminal_outcomes": result.get("terminal_outcome_count", 0),
        "joined_resolved": result.get("joined_resolved_forecast_count", 0),
        "errors": len(result.get("errors", [])),
        "warnings": result.get("warning_total_count", len(result.get("warnings", []))),
        "profitability_proven": False,
        "trade_authorized": False,
        "publication_authorized": False,
    }))
    return {"VERIFIED": 0, "BLOCKED": 2, "FAILED": 1}.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
