"""Build experiment-arm inputs only from exact, joined, validated evidence.

This is an evidence assembler, not a source of payout truth. Missing experiment
labels or invalid reward events remain gaps; no engagement metric is converted
into revenue.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nic_reward_evidence import canonical_post_id, is_verified_reward_event, reward_event_rejection_reasons

ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTION = ROOT / "analytics" / "publication_attribution.jsonl"
PERFORMANCE = ROOT / "analytics" / "square_performance.jsonl"
REWARDS = ROOT / "analytics" / "wte_reward_events.jsonl"
PLAN = ROOT / "analytics" / "creator_7_4_experiment_plan.json"
OUTPUT = ROOT / "analytics" / "creator_experiment_results.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _post_id(row: dict[str, Any]) -> str:
    return canonical_post_id(row)


def _arm(row: dict[str, Any], control_value: str, treatment_value: str) -> str:
    raw = str(row.get("experiment_arm") or row.get("variant") or row.get("treatment") or "").strip()
    if raw in {"control", "baseline", control_value, "__baseline__"}:
        return "control"
    if raw in {"candidate", "treatment", treatment_value, "data_driven_breakdown"}:
        return "candidate"
    return ""


def build_experiment_results(
    attribution_rows: list[dict[str, Any]],
    performance_rows: list[dict[str, Any]],
    reward_rows: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    current = plan.get("current_experiment") if isinstance(plan, dict) else None
    if not isinstance(current, dict) or not str(current.get("experiment_id") or "").strip():
        return {"schema_version": "1.0", "status": "INPUT_MISSING_OR_INVALID", "experiments": [],
                "reasons": ["active_experiment_plan_missing"], "generated_at": datetime.now(timezone.utc).isoformat()}

    experiment_id = str(current["experiment_id"]).strip()
    control_value = str(current.get("control_value") or "__baseline__")
    treatment_value = str(current.get("treatment_value") or "")
    performance_by_post: dict[str, dict[str, Any]] = {}
    for row in performance_rows:
        pid = _post_id(row)
        if pid:
            # Last observed row for a post wins; never join by symbol alone.
            performance_by_post[pid] = row

    arms: dict[str, dict[str, Any]] = {
        "control": {"post_ids": set(), "views": 0, "engagements": 0, "reward_posts": set(), "reward_amount": 0.0, "evidence_refs": []},
        "candidate": {"post_ids": set(), "views": 0, "engagements": 0, "reward_posts": set(), "reward_amount": 0.0, "evidence_refs": []},
    }
    rejected_rewards: dict[str, int] = defaultdict(int)
    joined_posts: dict[str, str] = {}
    seen_attribution: dict[str, str] = {}
    conflicting_posts: set[str] = set()
    rejected_attribution_rows: dict[str, int] = defaultdict(int)

    for row in attribution_rows:
        if str(row.get("experiment_id") or "").strip() != experiment_id:
            continue
        # An assigned arm is not evidence that the writer applied its treatment.
        # Only publisher attribution explicitly confirmed APPLIED may enter learning.
        if str(row.get("experiment_application_status") or "").strip().upper() != "APPLIED":
            rejected_attribution_rows["experiment_application_not_confirmed"] += 1
            continue
        pid = _post_id(row)
        arm_name = _arm(row, control_value, treatment_value)
        if not pid or not arm_name or pid not in performance_by_post:
            continue
        perf = performance_by_post[pid]
        if perf.get("metrics_verified") is not True:
            continue
        if pid in conflicting_posts:
            continue
        previous_arm = seen_attribution.get(pid)
        if previous_arm:
            if previous_arm != arm_name:
                # Conflicting arm assignments make the post unusable for either arm.
                arms[previous_arm]["post_ids"].discard(pid)
                joined_posts.pop(pid, None)
                conflicting_posts.add(pid)
            # Duplicate attribution rows must never inflate sample sizes or metrics.
            continue
        seen_attribution[pid] = arm_name
        arm = arms[arm_name]
        arm["post_ids"].add(pid)
        joined_posts[pid] = arm_name
        metrics = perf.get("metrics") if isinstance(perf.get("metrics"), dict) else perf
        views = _nonnegative_int(metrics.get("views"))
        engagements = sum(_nonnegative_int(metrics.get(key)) for key in ("likes", "comments", "shares", "quotes"))
        arm["views"] += views
        arm["engagements"] += engagements

    # Only validator-approved reward rows attached to a post in an arm count.
    seen_reward_ids: set[str] = set()
    for row in reward_rows:
        event_id = str(row.get("event_id") or "").strip()
        if event_id and event_id in seen_reward_ids:
            rejected_rewards["duplicate_reward_event_id"] += 1
            continue
        if event_id:
            seen_reward_ids.add(event_id)
        pid = _post_id(row)
        reasons = reward_event_rejection_reasons(row)
        if reasons:
            for reason in reasons:
                rejected_rewards[reason] += 1
            continue
        arm_name = joined_posts.get(pid)
        if not arm_name:
            rejected_rewards["verified_reward_not_joined_to_experiment_post"] += 1
            continue
        arm = arms[arm_name]
        arm["reward_posts"].add(pid)
        arm["reward_amount"] += float(row["reward_amount_usdc"])
        arm["evidence_refs"].extend(row["evidence_refs"])

    def serialize(name: str) -> dict[str, Any]:
        arm = arms[name]
        return {
            "post_count": len(arm["post_ids"]),
            "views": arm["views"],
            "engagements": arm["engagements"],
            "verified_reward_post_count": len(arm["reward_posts"]),
            "verified_reward_amount_usdc": round(arm["reward_amount"], 8) if arm["reward_posts"] else None,
            "reward_evidence_refs": arm["evidence_refs"],
            "post_ids": sorted(arm["post_ids"]),
        }

    control = serialize("control")
    candidate = serialize("candidate")
    status = "READY_FOR_EVALUATION" if control["post_count"] or candidate["post_count"] else "NO_EXPERIMENT_ATTRIBUTION"
    return {
        "schema_version": "1.0",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_counts": {
            "attribution_rows": len(attribution_rows),
            "performance_rows": len(performance_rows),
            "reward_rows": len(reward_rows),
            "experiment_attributed_posts_joined": len(joined_posts),
            "conflicting_arm_assignment_posts": len(conflicting_posts),
            "rejected_attribution_reasons": dict(sorted(rejected_attribution_rows.items())),
            "rejected_reward_reasons": dict(sorted(rejected_rewards.items())),
        },
        "experiments": [{
            "experiment_id": experiment_id,
            "control": control,
            "candidate": candidate,
            "evidence_policy": "exact_post_id_join; verified metrics; rewards must pass nic_reward_evidence validator",
        }],
        "publication_authorized": False,
        "strategy_auto_promoted": False,
    }


def _nonnegative_int(value: Any) -> int:
    try:
        number = int(value)
        return number if number >= 0 else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def main() -> int:
    try:
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        plan = {}
    report = build_experiment_results(read_jsonl(ATTRIBUTION), read_jsonl(PERFORMANCE), read_jsonl(REWARDS), plan)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report.get("status"), "output": str(OUTPUT), "source_counts": report.get("source_counts", {})}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
