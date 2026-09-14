"""Creator 8.3 — Verified Monetization Decision Engine.

Turns repeated, explicitly attributed monetization observations from Creator 8.2
into bounded hypotheses for Creator 7.4/7.5. Revenue is a secondary signal:
it can nominate an experiment, never force a story, guarantee an outcome, or
override editorial/safety gates.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "analytics/creator_8_0_monetization_engine.json"
PLAN = ROOT / "analytics/creator_7_4_experiment_plan.json"
MEMORY = ROOT / "analytics/strategy_memory.json"
OUT = ROOT / "analytics/creator_8_3_monetization_decision.json"
REPORT = ROOT / "data/intelligence/creator_8_3_report.json"

MIN_RECORDS = 3
MIN_CONVERSIONS = 1


def load(path: Path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def num(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else 0.0
    except Exception:
        return 0.0


def repeated_signals(doc):
    rows = doc.get("repeated_monetization_signals", []) if isinstance(doc, dict) else []
    return [x for x in rows if isinstance(x, dict) and int(x.get("records", 0) or 0) >= MIN_RECORDS]


def choose_signal(rows):
    candidates = []
    for row in rows:
        revenue = num(row.get("verified_revenue"))
        conversions = num(row.get("verified_conversions"))
        records = int(row.get("records", 0) or 0)
        if revenue <= 0 and conversions < MIN_CONVERSIONS:
            continue
        # Revenue is useful only as repeated evidence; sample size and outcome
        # quality prevent a single large observation from dominating.
        score = math.log1p(max(revenue, 0.0)) * 2 + math.log1p(records) * 8
        score += min(num(row.get("median_outcome_score")), 100) * 0.25
        score += min(conversions, 20) * 2
        candidates.append((score, row))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def current_plan():
    doc = load(PLAN, {})
    current = doc.get("current_experiment") if isinstance(doc, dict) else None
    return current if isinstance(current, dict) else None


def build_hypothesis(signal):
    dim = str(signal.get("dimension") or "")
    value = str(signal.get("value") or "")
    if dim not in {"format", "experiment_format", "hook_type", "thesis_type", "signal_type", "story_lane", "market_regime", "visual_type", "category"}:
        return None
    if value in {"", "unknown"}:
        return None
    return {
        "primary_variable": dim,
        "treatment_value": value,
        "hypothesis": f"Repeated verified monetization has been observed when {dim}={value}; test whether this pattern replicates on naturally qualified stories without forcing the format or asset.",
        "evidence": {
            "records": int(signal.get("records", 0) or 0),
            "verified_revenue": num(signal.get("verified_revenue")),
            "verified_conversions": num(signal.get("verified_conversions")),
            "median_outcome_score": num(signal.get("median_outcome_score")),
            "evidence_type": "DESCRIPTIVE_REPEATED",
        },
    }


def main():
    now = datetime.now(timezone.utc).isoformat()
    source = load(SOURCE, {})
    signals = repeated_signals(source)
    signal = choose_signal(signals)
    current = current_plan()

    decision = "NO_MONETIZATION_HYPOTHESIS"
    nominated = None
    if signal:
        nominated = build_hypothesis(signal)

    # Never replace an active experiment. Revenue may nominate a future test,
    # but an existing controlled lifecycle owns the experiment slot.
    if isinstance(current, dict) and current.get("status") == "ACTIVE":
        decision = "PRESERVE_ACTIVE_EXPERIMENT"
        applied = current.get("experiment_id")
    elif nominated:
        experiment_id = f"83-revenue-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        plan = {
            "experiment_id": experiment_id,
            "status": "ACTIVE",
            "created_at": now,
            "mode": "REVENUE_REPLICATION",
            "hypothesis": nominated["hypothesis"],
            "primary_variable": nominated["primary_variable"],
            "control_value": "__baseline__",
            "treatment_value": nominated["treatment_value"],
            "objective_metric": "outcome_score",
            "secondary_metrics": ["views", "likes", "comments", "shares", "quotes", "follower_growth", "verified_conversions", "verified_revenue"],
            "sample_target": 10,
            "minimum_explicit_observations_for_evaluation": 6,
            "revenue_evidence": nominated["evidence"],
            "application_policy": "Apply only when the naturally selected story supports the treatment. Never manufacture a story, asset, click or trade outcome to complete this experiment.",
            "attribution_policy": "Explicit experiment_id attribution is required for completion. Revenue must remain explicitly verified.",
            "promotion_policy": "Promotion requires independent replication plus editorial-quality evidence; revenue alone cannot promote a strategy.",
            "safety_constraints": ["factual_accuracy", "originality", "verified_market_data", "no_guaranteed_returns", "no_market_manipulation", "no_clickbait"],
        }
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps({
            "version": "8.3-bridge",
            "generated_at": now,
            "status": "ACTIVE",
            "decision": "START_REVENUE_REPLICATION",
            "current_experiment": plan,
            "completed_experiments": [],
            "last_evaluation": {"status": "NOMINATED_FROM_REPEATED_VERIFIED_MONETIZATION"},
            "controller_policy": {"revenue_is_secondary": True, "never_force_story": True, "explicit_attribution_required": True},
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        decision = "START_REVENUE_REPLICATION"
        applied = experiment_id
    else:
        applied = current.get("experiment_id") if current else None

    result = {
        "version": "8.3",
        "generated_at": now,
        "decision": decision,
        "repeated_signal_count": len(signals),
        "selected_signal": signal,
        "applied_experiment_id": applied,
        "policy": {
            "minimum_repeated_records": MIN_RECORDS,
            "revenue_is_secondary_signal": True,
            "causal_claims_allowed": False,
            "independent_replication_required": True,
            "never_force_weak_story": True,
            "never_infer_revenue": True,
            "never_override_editorial_or_safety_gates": True,
        },
        "next_step": "Let Creator 7.4 evaluate the naturally occurring experiment; let Creator 7.5 allocate portfolio mix only after quality evidence accumulates.",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    memory = load(MEMORY, {})
    overlay = memory.get("learning_overlay") if isinstance(memory.get("learning_overlay"), dict) else {}
    overlay["monetization_decision_engine"] = {
        "version": "8.3",
        "decision": decision,
        "experiment_id": applied,
        "repeated_signal_count": len(signals),
        "updated_at": now,
        "revenue_inference_disabled": True,
        "story_forcing_disabled": True,
    }
    memory["learning_overlay"] = overlay
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "OK",
        "version": "8.3",
        "decision": decision,
        "repeated_signals": len(signals),
        "experiment_id": applied,
        "report": str(REPORT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
