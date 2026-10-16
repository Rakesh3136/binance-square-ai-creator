"""Build an auditable, evidence-grounded distillation dataset for NIC.

This prepares examples for later teacher/student fine-tuning; it does not call an
LLM, fine-tune a model, or authorize trades/publication. Teacher explanations
must be concise decision summaries, never private chain-of-thought.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
INTEL = ROOT / "data/intelligence"
INPUTS = (
    LIVE / "nic_distillation_teacher_examples.jsonl",
    LIVE / "nic_distillation_reviewed_examples.jsonl",
)
TRAIN_OUT = INTEL / "nic_distillation_train.jsonl"
EVAL_OUT = INTEL / "nic_distillation_eval.jsonl"
REPORT_OUT = INTEL / "nic_distillation_report.json"
APPROVED_LABELS = {"ACCEPT", "REJECT", "REVISE", "WIN", "LOSS", "AMBIGUOUS", "UNKNOWN"}
VERIFIED_STATES = {"VERIFIED", "REVIEWED", "CONFIRMED"}
GUARDRAILS = {
    "fine_tuning_performed": False,
    "trade_authorized": False,
    "publication_authorized": False,
    "learning_may_bypass_quality_gates": False,
    "views_are_not_revenue": True,
    "outcome_labels_require_terminal_evidence": True,
    "teacher_rationale_is_summary_not_chain_of_thought": True,
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        pass
    return rows


def evidence_is_grounded(row: dict[str, Any]) -> bool:
    refs = row.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False
    grounded = False
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        has_source = bool(str(ref.get("url") or ref.get("source_id") or "").strip())
        has_integrity = bool(str(ref.get("sha256") or ref.get("excerpt_hash") or "").strip())
        has_time = parse_time(ref.get("observed_at")) is not None
        grounded = grounded or (has_source and has_integrity and has_time)
    return grounded


def validate_example(row: dict[str, Any]) -> list[str]:
    issues = []
    for key in ("example_id", "task_type", "input", "teacher_target", "created_at"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"missing_{key}")
    if not parse_time(row.get("created_at")):
        issues.append("invalid_created_at")
    if not evidence_is_grounded(row):
        issues.append("missing_timestamped_hashed_evidence")
    if str(row.get("review_status") or "").upper() not in VERIFIED_STATES:
        issues.append("not_reviewed_or_verified")
    label = str(row.get("label") or "").upper()
    if label not in APPROVED_LABELS:
        issues.append("unsupported_label")
    if row.get("task_type") == "forecast_outcome":
        if str(row.get("outcome_status") or "").upper() != "TERMINAL_VERIFIED":
            issues.append("forecast_outcome_not_terminal_verified")
        if not row.get("forecast_id"):
            issues.append("missing_forecast_id")
    if row.get("task_type") == "creator_reward":
        if str(row.get("reward_status") or "").upper() not in {"PAID_VERIFIED", "REWARD_VERIFIED"}:
            issues.append("creator_reward_not_verified")
        if not row.get("canonical_post_id"):
            issues.append("missing_canonical_post_id")
    # Prevent future information leaking into the student input.
    input_text = str(row.get("input") or "").lower()
    if row.get("task_type") == "forecast_outcome" and any(
        token in input_text for token in ("realized outcome:", "final result:", "terminal label:")
    ):
        issues.append("outcome_leakage_in_input")
    return issues


def build_dataset(
    examples: Iterable[dict[str, Any]], eval_fraction: float = 0.2
) -> dict[str, Any]:
    if not 0.05 <= eval_fraction <= 0.4:
        raise ValueError("eval_fraction must be between 0.05 and 0.4")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in examples:
        issues = validate_example(row)
        eid = str(row.get("example_id") or "").strip()
        if eid and eid in seen_ids:
            issues.append("duplicate_example_id")
        if eid:
            seen_ids.add(eid)
        if issues:
            rejected.append({"example_id": eid or None, "reasons": sorted(set(issues))})
            continue
        created = parse_time(row["created_at"])
        assert created is not None
        # Keep only the fields needed for supervised distillation; do not pass
        # source payloads or post-outcome data into the student's prompt.
        accepted.append({
            "example_id": eid,
            "task_type": row["task_type"],
            "input": row["input"].strip(),
            "target": row["teacher_target"].strip(),
            "label": str(row["label"]).upper(),
            "created_at": created.isoformat(),
            "evidence_digest": digest(row["evidence_refs"]),
            "source_group": str(row.get("source_group") or eid),
        })
    accepted.sort(key=lambda r: (r["created_at"], r["example_id"]))
    # Split by time and source group: one source group cannot appear in both
    # train and evaluation, preventing simple near-duplicate leakage.
    groups = []
    for row in accepted:
        if row["source_group"] not in groups:
            groups.append(row["source_group"])
    eval_count = max(1, int(round(len(groups) * eval_fraction))) if len(groups) >= 2 else 0
    eval_groups = set(groups[-eval_count:]) if eval_count else set()
    train = [r for r in accepted if r["source_group"] not in eval_groups]
    evaluation = [r for r in accepted if r["source_group"] in eval_groups]
    # Hashes are metadata only; they do not imply model quality.
    return {
        "schema": "NIC-DISTILLATION-DATASET-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "DATASET_READY_FOR_REVIEW" if train and evaluation else "BLOCKED_INSUFFICIENT_VERIFIED_DATA",
        "train": train,
        "evaluation": evaluation,
        "rejected": rejected,
        "summary": {
            "accepted": len(accepted),
            "train": len(train),
            "evaluation": len(evaluation),
            "rejected": len(rejected),
            "labels": dict(Counter(r["label"] for r in accepted)),
            "source_groups_train": len({r["source_group"] for r in train}),
            "source_groups_eval": len({r["source_group"] for r in evaluation}),
            "split_group_overlap": bool({r["source_group"] for r in train} & {r["source_group"] for r in evaluation}),
            "dataset_sha256": digest(accepted),
        },
        "guardrails": GUARDRAILS,
        "promotion_policy": {
            "require_human_review": True,
            "require_held_out_eval": True,
            "require_baseline_comparison": True,
            "require_chronological_forecast_eval_after_costs": True,
            "minimum_verified_examples_for_training": 100,
            "minimum_held_out_examples_for_promotion": 25,
            "insufficient_data_action": "DO_NOT_TRAIN_OR_PROMOTE",
        },
        "limitations": [
            "Dataset construction is not model fine-tuning.",
            "A teacher can be wrong; teacher outputs require evidence and review.",
            "Do not use views as a revenue label or unresolved forecasts as outcomes.",
            "Small or imbalanced datasets are blocked from promotion.",
        ],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> int:
    examples = []
    for path in INPUTS:
        examples.extend(read_jsonl(path))
    result = build_dataset(examples)
    write_jsonl(TRAIN_OUT, result["train"])
    write_jsonl(EVAL_OUT, result["evaluation"])
    INTEL.mkdir(parents=True, exist_ok=True)
    report = {k: v for k, v in result.items() if k not in {"train", "evaluation"}}
    REPORT_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"], "guardrails": GUARDRAILS}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
