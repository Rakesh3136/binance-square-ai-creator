"""Creator 7.4 — Adaptive Experiment Controller v2.

Turns Creator 7.3 matched observational learning into a bounded experiment
lifecycle. It keeps one primary variable per test, avoids changing an active
test every run, evaluates completed tests only when attribution is adequate,
and then chooses replication or exploration. It never forces weak stories.

This is an editorial learning controller, not a market-prediction engine.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "analytics/creator_7_2_outcomes.jsonl"
CAUSAL = ROOT / "analytics/creator_7_3_strategy.json"
MEMORY = ROOT / "analytics/strategy_memory.json"
PLAN = ROOT / "analytics/creator_7_4_experiment_plan.json"
REPORT = ROOT / "data/intelligence/creator_7_4_report.json"

BASE_DIMS = ("experiment_format", "category", "style", "hook_type", "visual_type")
OPTIONAL_DIMS = ("thesis_type", "signal_type", "story_lane", "market_regime")
TARGET = 10
MIN_COMPLETION = 6


def load_json(path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def rows():
    if not SOURCE.exists():
        return []
    out = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict) and isinstance(x.get("metrics"), dict):
                out.append(x)
        except Exception:
            pass
    return out


def num(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else 0.0
    except Exception:
        return 0.0


def outcome(x):
    if x.get("outcome_score") is not None:
        return num(x["outcome_score"])
    m = x.get("metrics") or {}
    views = num(m.get("views"))
    if views <= 0:
        return 0.0
    return (num(m.get("likes")) + 2*num(m.get("comments")) + 3*num(m.get("shares")) + 2*num(m.get("quotes"))) / views * 1000


def median(values):
    values = sorted(values)
    if not values:
        return 0.0
    n = len(values)
    return values[n//2] if n % 2 else (values[n//2-1] + values[n//2]) / 2


def row_time(row):
    for key in ("published_at", "created_at", "timestamp", "time", "observed_at"):
        value = row.get(key)
        if not value:
            continue
        try:
            text = str(value).replace("Z", "+00:00")
            return datetime.fromisoformat(text).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def experiment_id(row):
    for key in ("experiment_id", "creator_7_4_experiment_id"):
        value = row.get(key)
        if value:
            return str(value)
    for container in (row.get("experiment"), row.get("learning"), row.get("metadata")):
        if isinstance(container, dict) and container.get("experiment_id"):
            return str(container["experiment_id"])
    return ""


def explicit_observations(data, current):
    """Prefer explicit experiment attribution; never fabricate attribution."""
    exp_id = str(current.get("experiment_id") or "")
    if not exp_id:
        return []
    return [x for x in data if experiment_id(x) == exp_id]


def proxy_observations(data, current):
    """Fallback diagnostics only; these are never treated as completion proof."""
    dim = str(current.get("primary_variable") or "")
    value = str(current.get("treatment_value") or "")
    created = row_time(current) or None
    out = []
    for x in data:
        if created and row_time(x) and row_time(x) < created:
            continue
        if dim and str(x.get(dim) or "unknown") == value:
            out.append(x)
    return out


def test_result(data, current):
    treated = explicit_observations(data, current)
    attribution = "EXPLICIT"
    if not treated:
        treated = proxy_observations(data, current)
        attribution = "PROXY_DIAGNOSTIC_ONLY"
    if not treated:
        return {"status": "NO_OBSERVATIONS", "attribution": attribution, "sample": 0}

    treatment_scores = [outcome(x) for x in treated]
    controls = []
    dim = str(current.get("primary_variable") or "")
    value = str(current.get("treatment_value") or "")
    for x in data:
        if x in treated:
            continue
        if dim and str(x.get(dim) or "unknown") == value:
            continue
        controls.append(outcome(x))

    result = {
        "status": "READY_TO_EVALUATE" if attribution == "EXPLICIT" and len(treated) >= MIN_COMPLETION else "ACTIVE",
        "attribution": attribution,
        "sample": len(treated),
        "target": int(current.get("sample_target") or TARGET),
        "treatment_median": round(median(treatment_scores), 4),
        "control_sample": len(controls),
        "control_median": round(median(controls), 4) if controls else 0.0,
        "lift_percent": round((median(treatment_scores) - median(controls)) / max(abs(median(controls)), 1) * 100, 2) if controls else 0.0,
        "explicit_attribution": attribution == "EXPLICIT",
    }
    return result


def available_dimensions(data):
    dims = list(BASE_DIMS)
    for dim in OPTIONAL_DIMS:
        if sum(bool(str(row.get(dim) or "").strip()) for row in data) >= 6:
            dims.append(dim)
    return tuple(dict.fromkeys(dims))


def raw_effect(data, dim, value):
    treated = [outcome(x) for x in data if str(x.get(dim) or "unknown") == value]
    control = [outcome(x) for x in data if str(x.get(dim) or "unknown") != value]
    if len(treated) < 3 or len(control) < 3:
        return None
    tm, cm = median(treated), median(control)
    lift = tm - cm
    return {
        "dimension": dim,
        "value": value,
        "treated_sample": len(treated),
        "control_sample": len(control),
        "treated_median": round(tm, 4),
        "control_median": round(cm, 4),
        "lift_percent": round(lift / max(abs(cm), 1) * 100, 2),
    }


def matched_effect(data, dim, value):
    by_asset = defaultdict(list)
    for row in data:
        asset = str(row.get("symbol") or row.get("asset") or "").strip().upper()
        if asset:
            by_asset[asset].append(row)
    differences = []
    for items in by_asset.values():
        treated = [outcome(x) for x in items if str(x.get(dim) or "unknown") == value]
        control = [outcome(x) for x in items if str(x.get(dim) or "unknown") != value]
        if treated and control:
            differences.append(median(treated) - median(control))
    if len(differences) < 3:
        return None
    lift = median(differences)
    return {"matched_assets": len(differences), "matched_median_lift_points": round(lift, 4)}


def choose_experiment(data, causal, completed):
    recommendations = causal.get("recommendations", []) if isinstance(causal, dict) else {}
    winners = [x for x in recommendations if isinstance(x, dict) and x.get("decision") == "PREFER"]
    winners.sort(key=lambda x: (num(x.get("lift_percent")), int(x.get("treated_sample", 0))), reverse=True)

    completed_keys = {(str(x.get("primary_variable")), str(x.get("treatment_value"))) for x in completed if isinstance(x, dict)}
    for w in winners:
        key = (str(w.get("dimension")), str(w.get("value")))
        if key not in completed_keys:
            return "REPLICATION", str(w.get("dimension")), str(w.get("value")), "Replicate a matched repeated winner before promoting it."

    candidates = []
    for dim in available_dimensions(data):
        values = sorted({str(x.get(dim) or "unknown") for x in data})
        for value in values:
            e = raw_effect(data, dim, value)
            if not e:
                continue
            matched = matched_effect(data, dim, value)
            matched_assets = matched.get("matched_assets", 0) if matched else 0
            uncertainty = 100 / max(e["treated_sample"], 1) + 50 / max(e["control_sample"], 1)
            ambiguity = 10 / (1 + abs(e["lift_percent"]))
            score = uncertainty + ambiguity + (20 if matched_assets < 3 else 0)
            candidates.append((score, dim, value))
    if candidates:
        candidates.sort(reverse=True)
        _, dim, value = candidates[0]
        return "EXPLORATION", dim, value, "Reduce uncertainty with one controlled editorial variable."
    return "EXPLORATION", "experiment_format", "data_driven_breakdown", "Cold-start with a platform-native evidence breakdown."


def build_plan(data, causal, memory):
    now = datetime.now(timezone.utc).isoformat()
    existing = load_json(PLAN, {})
    current = existing.get("current_experiment") if isinstance(existing, dict) else None
    history = existing.get("completed_experiments", []) if isinstance(existing, dict) else []
    if not isinstance(history, list):
        history = []

    # An active test remains stable until it has explicit outcome attribution.
    if isinstance(current, dict) and current.get("status") == "ACTIVE":
        result = test_result(data, current)
        if result.get("status") != "READY_TO_EVALUATE":
            return current, history, "continue_active_experiment", result

        completed = dict(current)
        completed["status"] = "COMPLETED"
        completed["completed_at"] = now
        completed["result"] = result
        history = (history + [completed])[-30:]
        # Completion is recorded, then a new plan is selected below.

    mode, dim, value, reason = choose_experiment(data, causal, history)
    exp_id = f"74-{mode.lower()[:3]}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    plan = {
        "experiment_id": exp_id,
        "status": "ACTIVE",
        "created_at": now,
        "mode": mode,
        "hypothesis": f"Test whether {dim}={value} improves outcome quality versus the account baseline while other major choices remain stable.",
        "primary_variable": dim,
        "control_value": "__baseline__",
        "treatment_value": value,
        "objective_metric": "outcome_score",
        "secondary_metrics": ["views", "likes", "comments", "shares", "quotes", "follower_growth"],
        "sample_target": TARGET,
        "minimum_explicit_observations_for_evaluation": MIN_COMPLETION,
        "reason": reason,
        "application_policy": "Apply only when the naturally selected story supports this variable. Never invent a weak story to complete an experiment.",
        "attribution_policy": "Only explicit experiment_id attribution can complete a test. Proxy matches are diagnostics and cannot close the lifecycle.",
        "stop_rules": [
            "Do not claim causality from observational evidence.",
            "Do not publish filler merely to reach sample_target.",
            "Do not override factual, originality, market-data, or safety gates.",
            "Do not infer revenue from engagement metrics.",
        ],
    }
    return plan, history, "start_new_experiment", {"status": "NEW", "completed_count": len(history)}


def main():
    data = rows()
    causal = load_json(CAUSAL, {})
    memory = load_json(MEMORY, {})
    plan, history, decision, result = build_plan(data, causal, memory)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "version": "7.4.1",
        "generated_at": now,
        "status": "ACTIVE",
        "decision": decision,
        "current_experiment": plan,
        "completed_experiments": history,
        "last_evaluation": result,
        "controller_policy": {
            "exploration_rate": 0.35 if len(data) < 30 else 0.20,
            "one_primary_variable_per_test": True,
            "prefer_matched_replication_before_promotion": True,
            "explicit_attribution_required_for_completion": True,
            "skip_if_no_quality_story": True,
            "revenue_policy": "Use revenue only when explicitly verified; never infer revenue from engagement.",
        },
        "hard_constraints": ["factual_accuracy", "originality", "verified_market_data", "no_fake_engagement", "no_guaranteed_returns", "no_market_manipulation"],
    }
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    memory["creator_7_4"] = doc
    overlay = memory.get("learning_overlay")
    if not isinstance(overlay, dict):
        overlay = {}
    overlay["adaptive_experiment_controller"] = {
        "instruction": "Use creator_7_4.current_experiment only when the naturally selected story supports it. Keep one primary variable stable. Never force weak stories, fake evidence, engagement, or returns.",
        "experiment_id": plan.get("experiment_id"),
        "primary_variable": plan.get("primary_variable"),
        "treatment_value": plan.get("treatment_value"),
        "mode": plan.get("mode"),
    }
    memory["learning_overlay"] = overlay
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")

    report = {
        "version": "7.4.1",
        "generated_at": now,
        "sample_size": len(data),
        "decision": decision,
        "next_experiment": plan,
        "completed_experiments": history[-10:],
        "last_evaluation": result,
        "policy": doc["controller_policy"],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "OK", "version": "7.4.1", "decision": decision, "experiment_id": plan.get("experiment_id"), "primary_variable": plan.get("primary_variable"), "treatment_value": plan.get("treatment_value"), "completed_experiments": len(history), "report": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
