"""Deterministic draft-time assignment for bounded creator experiments.

Assignments are metadata only until the writer confirms the treatment was applied.
This module never authorizes publication or strategy promotion.
"""
from __future__ import annotations

import hashlib
from typing import Any


def assign_experiment(plan: dict[str, Any], cycle_id: str) -> dict[str, Any]:
    current = plan.get("current_experiment") if isinstance(plan, dict) else None
    if not isinstance(current, dict):
        return {"status": "NO_ACTIVE_EXPERIMENT", "assigned": False}
    experiment_id = str(current.get("experiment_id") or "").strip()
    status = str(current.get("status") or plan.get("status") or "").strip().upper()
    variable = str(current.get("primary_variable") or "").strip()
    control = current.get("control_value")
    treatment = current.get("treatment_value")
    if status != "ACTIVE" or not experiment_id or not variable or control is None or treatment is None:
        return {"status": "NO_ACTIVE_EXPERIMENT", "assigned": False}
    seed = str(cycle_id or "").strip()
    if not seed:
        return {"status": "NO_STABLE_CYCLE_ID", "assigned": False, "experiment_id": experiment_id}
    digest = hashlib.sha256(f"{experiment_id}:{seed}".encode("utf-8")).hexdigest()
    arm = "control" if int(digest[:8], 16) % 2 == 0 else "candidate"
    value = control if arm == "control" else treatment
    return {
        "status": "ASSIGNED",
        "assigned": True,
        "experiment_id": experiment_id,
        "experiment_arm": arm,
        "experiment_variable": variable,
        "experiment_treatment": str(value),
        "control_value": str(control),
        "candidate_value": str(treatment),
        "assignment_seed_hash": digest,
        "assignment_method": "sha256_experiment_id_plus_cycle_id_parity",
        "application_status": "PENDING_WRITER_CONFIRMATION",
        "publication_authorized": False,
        "strategy_auto_promoted": False,
    }


def mark_treatment_applied(assignment: dict[str, Any], applied: bool) -> dict[str, Any]:
    result = dict(assignment)
    if result.get("assigned"):
        result["application_status"] = "APPLIED" if applied else "NOT_APPLIED"
    return result
