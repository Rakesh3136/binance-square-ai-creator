"""Creator 7.3 — Causal Strategy Optimizer v2.

Turns verified Creator 7.2 outcomes into bounded, causal-style hypotheses.
This is NOT a claim of scientific causality: observational evidence is
confounded easily in market content. The optimizer therefore adds matched
within-asset comparisons, agreement checks, stability checks, and explicit
promotion thresholds before a finding can influence future experiments.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analytics/creator_7_3_causal_effects.json"
REPORT = ROOT / "data/intelligence/creator_7_3_report.json"
STRATEGY = ROOT / "analytics/creator_7_3_strategy.json"
MEMORY = ROOT / "analytics/strategy_memory.json"
SOURCE = ROOT / "analytics/creator_7_2_outcomes.jsonl"

BASE_DIMS = ("experiment_format", "category", "style", "hook_type", "visual_type")
OPTIONAL_DIMS = ("thesis_type", "signal_type", "story_lane", "market_regime")


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


def num(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else 0.0
    except Exception:
        return 0.0


def outcome(row):
    if row.get("outcome_score") is not None:
        return num(row.get("outcome_score"))
    metrics = row.get("metrics") or {}
    views = num(metrics.get("views"))
    if views <= 0:
        return 0.0
    return (num(metrics.get("likes")) + 2*num(metrics.get("comments")) +
            3*num(metrics.get("shares")) + 2*num(metrics.get("quotes"))) / views * 1000


def median(values):
    values = sorted(values)
    if not values:
        return 0.0
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def quantile(values, q):
    values = sorted(values)
    if not values:
        return 0.0
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


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
        "lift_points": round(lift, 4),
        "lift_percent": round(lift / max(abs(cm), 1) * 100, 2),
    }


def matched_effect(data, dim, value):
    """Compare treatment/control inside the same asset where possible.

    This reduces a major crypto-content confounder: a format may look strong
    simply because it was used on better-performing assets. Each asset must
    contribute both treatment and control observations before its difference
    enters the aggregate estimate.
    """
    by_asset = defaultdict(list)
    for row in data:
        asset = str(row.get("symbol") or row.get("asset") or "").strip().upper()
        if asset:
            by_asset[asset].append(row)

    differences = []
    matched_assets = 0
    treatment_n = control_n = 0
    for asset, items in by_asset.items():
        treated = [outcome(x) for x in items if str(x.get(dim) or "unknown") == value]
        control = [outcome(x) for x in items if str(x.get(dim) or "unknown") != value]
        if not treated or not control:
            continue
        matched_assets += 1
        treatment_n += len(treated)
        control_n += len(control)
        differences.append(median(treated) - median(control))

    if matched_assets < 3:
        return None
    lift = median(differences)
    return {
        "matched_assets": matched_assets,
        "matched_treatment_sample": treatment_n,
        "matched_control_sample": control_n,
        "matched_median_lift_points": round(lift, 4),
        "matched_lift_percent": round(lift / max(abs(median([0.0] + differences)), 1) * 100, 2),
        "matched_difference_iqr": round(quantile(differences, 0.75) - quantile(differences, 0.25), 4),
    }


def enrich_effect(data, dim, value):
    raw = raw_effect(data, dim, value)
    if not raw:
        return None
    matched = matched_effect(data, dim, value)
    if matched:
        raw["matched"] = matched
        raw["evidence_alignment"] = (
            "AGREE" if (raw["lift_points"] >= 0) == (matched["matched_median_lift_points"] >= 0)
            else "DISAGREE"
        )
    else:
        raw["matched"] = None
        raw["evidence_alignment"] = "UNMATCHED"
    return raw


def available_dimensions(data):
    dims = list(BASE_DIMS)
    for dim in OPTIONAL_DIMS:
        if sum(bool(str(row.get(dim) or "").strip()) for row in data) >= 6:
            dims.append(dim)
    return tuple(dict.fromkeys(dims))


def build_recommendations(effects):
    recommendations = []
    for effect in effects:
        matched = effect.get("matched") or {}
        raw_ok = effect.get("treated_sample", 0) >= 5 and effect.get("control_sample", 0) >= 5
        matched_ok = matched.get("matched_assets", 0) >= 3 and matched.get("matched_treatment_sample", 0) >= 5
        meaningful = abs(effect.get("lift_percent", 0)) >= 15
        aligned = effect.get("evidence_alignment") == "AGREE"
        # A preference is stronger only when the broad estimate and the
        # within-asset estimate point in the same direction.
        if raw_ok and matched_ok and meaningful and aligned:
            recommendations.append({
                **effect,
                "decision": "PREFER" if effect["lift_points"] > 0 else "DEPRIORITIZE",
                "confidence": "OBSERVATIONAL_MATCHED_REPEATED",
                "promotion_rule": "Hypothesis only; require a fresh controlled replication before treating as a stable strategy preference.",
            })
    return recommendations


def main():
    data = rows()
    dimensions = available_dimensions(data)
    effects = []
    for dim in dimensions:
        values = sorted({str(row.get(dim) or "unknown") for row in data})
        for value in values:
            effect = enrich_effect(data, dim, value)
            if effect:
                effects.append(effect)

    effects.sort(key=lambda x: (
        x.get("evidence_alignment") == "AGREE",
        x.get("matched", {}).get("matched_assets", 0) if isinstance(x.get("matched"), dict) else 0,
        x.get("lift_points", 0),
    ), reverse=True)
    recommendations = build_recommendations(effects)
    now = datetime.now(timezone.utc).isoformat()

    strategy = {
        "version": "7.3.1",
        "generated_at": now,
        "status": "ACTIVE" if len(data) >= 10 else "EXPLORATION",
        "sample_size": len(data),
        "dimensions_tested": list(dimensions),
        "effects": effects[:150],
        "recommendations": recommendations[:30],
        "causal_claim_policy": "Observational evidence is a hypothesis. Matched within-asset agreement reduces confounding but does not prove causality. Fresh controlled replication is required before stable promotion.",
        "exploration_rate": 0.20 if len(data) >= 30 else 0.35,
        "minimum_treatment_sample": 5,
        "minimum_control_sample": 5,
        "minimum_matched_assets": 3,
        "minimum_absolute_lift_percent": 15,
        "hard_constraints": [
            "factual_accuracy", "originality", "verified_market_data",
            "no_fake_engagement", "no_guaranteed_returns", "no_market_manipulation",
        ],
    }

    STRATEGY.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps({"generated_at": now, "version": "7.3.1", "effects": effects}, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "version": "7.3.1",
        "generated_at": now,
        "sample_size": len(data),
        "dimensions_tested": list(dimensions),
        "top_effects": effects[:30],
        "recommendations": recommendations[:30],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    memory = load_json(MEMORY, {})
    memory["creator_7_3"] = strategy
    memory.setdefault("learning_overlay", {})
    if isinstance(memory["learning_overlay"], dict):
        memory["learning_overlay"]["creator_7_3"] = {
            "instruction": "Use matched repeated effects as hypotheses for the next controlled experiment. Never force a story to satisfy an experiment and never convert an observational effect into a market prediction.",
            "recommendation_count": len(recommendations),
        }
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "OK",
        "version": "7.3.1",
        "sample_size": len(data),
        "dimensions_tested": len(dimensions),
        "effects_measured": len(effects),
        "matched_effects": sum(bool(e.get("matched")) for e in effects),
        "aligned_effects": sum(e.get("evidence_alignment") == "AGREE" for e in effects),
        "recommendations": len(recommendations),
        "report": str(REPORT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
