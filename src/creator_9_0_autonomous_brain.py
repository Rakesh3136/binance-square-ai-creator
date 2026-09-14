"""Creator 9.1 — Autonomous Strategy Orchestrator.

Creator 9.0 was previously a thin decision helper. This version becomes the
strategy layer above the existing 7.x learning/experiment portfolio and 8.x
verified-monetization feedback systems.

It does NOT publish, select arbitrary assets, or bypass hard gates. It emits a
bounded strategy brief that downstream editorial/opportunity gates can use.
WAIT is always a valid outcome.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "analytics/strategy_memory.json"
PERF = ROOT / "data/intelligence/performance_feedback.json"
BRAIN = ROOT / "data/live/creator_brain_decision.json"
MISSION = ROOT / "data/live/creator_mission_7.json"
AUTHORITATIVE = ROOT / "data/live/authoritative_opportunity.json"
EXPERIMENT = ROOT / "analytics/creator_7_4_experiment_plan.json"
GROWTH = ROOT / "analytics/creator_7_5_growth_portfolio.json"
MONETIZATION = ROOT / "analytics/creator_8_3_monetization_decision.json"
OUT = ROOT / "data/live/creator_9_0_brain_state.json"
BRIEF = ROOT / "data/live/creator_9_0_strategy_brief.json"
REPORT = ROOT / "data/intelligence/creator_9_0_report.json"


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


def clean_symbol(value):
    text = str(value or "").upper().strip()
    for suffix in ("/USDT", "USDT"):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return text


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def infer_regime(auth, perf, memory):
    """Use supplied regime evidence only; never manufacture a regime label."""
    candidates = [
        auth.get("market_regime"),
        auth.get("regime"),
        perf.get("market_regime"),
        perf.get("regime"),
    ]
    overlay = memory.get("learning_overlay")
    if isinstance(overlay, dict):
        candidates.extend([overlay.get("market_regime"), overlay.get("regime")])
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def recent_assets(memory):
    rows = memory.get("recent_performance_observations") or []
    assets = []
    for row in rows:
        if isinstance(row, dict):
            asset = clean_symbol(row.get("topic") or row.get("symbol") or row.get("asset"))
            if asset:
                assets.append(asset)
    return assets


def strategy_preferences(perf):
    learned = perf.get("learned_preferences")
    if not isinstance(learned, dict):
        return []
    out = []
    for dimension, info in learned.items():
        if not isinstance(info, dict) or not info.get("prefer"):
            continue
        out.append({
            "dimension": str(dimension),
            "value": str(info.get("prefer")),
            "reason": first_text(info.get("reason"), "repeated evidence"),
        })
    return out[:12]


def experiment_context(plan, monetization):
    current = plan.get("current_experiment") if isinstance(plan, dict) else None
    if not isinstance(current, dict) or current.get("status") != "ACTIVE":
        current = None
    decision = monetization.get("decision") if isinstance(monetization, dict) else None
    nominated = monetization.get("applied_experiment_id") if isinstance(monetization, dict) else None
    return {
        "active": bool(current),
        "experiment_id": current.get("experiment_id") if current else None,
        "primary_variable": current.get("primary_variable") if current else None,
        "treatment_value": current.get("treatment_value") if current else None,
        "mode": current.get("mode") if current else None,
        "monetization_decision": decision,
        "monetization_experiment_id": nominated,
        "use_policy": "apply only when naturally supported by the selected story",
    }


def choose_lane(auth, mission, growth):
    category = first_text(auth.get("category"), auth.get("content_category"), auth.get("story_lane"))
    if category:
        return category
    bucket = first_text(growth.get("recommended_bucket"), growth.get("active_bucket")) if isinstance(growth, dict) else ""
    if bucket:
        return bucket
    goal = first_text(mission.get("primary_goal"), mission.get("goal"))
    if goal:
        return goal
    return "research"


def main():
    now = datetime.now(timezone.utc).isoformat()
    memory = load(MEMORY, {})
    perf = load(PERF, {})
    brain = load(BRAIN, {})
    mission = load(MISSION, {})
    auth = load(AUTHORITATIVE, {})
    experiment = load(EXPERIMENT, {})
    growth = load(GROWTH, {})
    monetization = load(MONETIZATION, {})

    symbol = clean_symbol(auth.get("symbol") or brain.get("symbol"))
    sample = int(num(perf.get("observation_count")))
    promotion = bool(perf.get("promotion_allowed", False))
    regime = infer_regime(auth, perf, memory)
    assets = recent_assets(memory)
    counts = Counter(assets)
    pressure_asset, pressure_count = counts.most_common(1)[0] if counts else ("", 0)
    same_asset_pressure = bool(symbol and pressure_asset == symbol and pressure_count >= 2)

    mission_decision = first_text(mission.get("decision"), brain.get("decision"))
    lane = choose_lane(auth, mission, growth)
    preferences = strategy_preferences(perf)
    exp = experiment_context(experiment, monetization)

    # Hard hierarchy: validity/editorial gates first; then fresh opportunity;
    # then portfolio diversity and learning; monetization remains secondary.
    if not symbol:
        action = "WAIT_FOR_VALID_OPPORTUNITY"
        confidence = "LOW"
        reason = "No authoritative asset is available."
    elif same_asset_pressure and not bool(auth.get("news_authoritative")):
        action = "PIVOT_IF_ALTERNATIVE_IS_STRONGER"
        confidence = "MEDIUM"
        reason = "Recent asset concentration is high and no material authoritative update is present."
    elif mission_decision == "PUBLISH" and auth.get("binance_verified") is not False:
        action = "PUBLISH_STRONG_OPPORTUNITY"
        confidence = "HIGH" if sample >= 10 and promotion else "MEDIUM"
        reason = "The existing mission and authoritative opportunity support publication; downstream gates still decide."
    else:
        action = "RESEARCH_OR_WAIT"
        confidence = "LOW"
        reason = "No sufficiently strong publish directive is available at the strategy layer."

    # A controlled experiment is a preference, never a publication requirement.
    experiment_instruction = (
        "Preserve the active experiment and apply it only when the naturally selected story supports the treatment."
        if exp["active"] else
        "No active experiment: exploration may proceed only when a qualified story exists."
    )
    monetization_signal = {
        "decision": monetization.get("decision"),
        "experiment_id": monetization.get("applied_experiment_id"),
        "is_secondary": True,
        "verified_only": True,
        "can_override_editorial": False,
    }

    strategy = {
        "version": "9.1",
        "generated_at": now,
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "primary_asset": symbol,
        "story_lane": lane,
        "market_regime": regime,
        "observation_sample": sample,
        "promotion_allowed": promotion,
        "recent_asset_pressure": {
            "asset": pressure_asset,
            "recent_count": pressure_count,
            "avoid_repetition": same_asset_pressure,
        },
        "strategy_preferences": preferences,
        "experiment": exp,
        "monetization_feedback": monetization_signal,
        "decision_order": [
            "hard_validity_and_safety",
            "authoritative_fresh_opportunity",
            "editorial_value",
            "portfolio_diversity",
            "story_quality",
            "repeated_learning",
            "controlled_experiment",
            "verified_monetization",
            "exploration",
        ],
        "publisher_directive": {
            "publish_permission": action == "PUBLISH_STRONG_OPPORTUNITY",
            "choose_only_authoritative_frozen_asset": True,
            "prefer_fresh_verified_evidence": True,
            "avoid_repetitive_asset_or_lane": True,
            "use_real_market_data": True,
            "use_visual_proof_when_informative": True,
            "apply_one_experiment_variable_only": True,
            "experiment_instruction": experiment_instruction,
            "optimize_for_substantive_reader_value": True,
            "verified_conversion_and_revenue_are_secondary": True,
            "never_force_story_for_experiment_or_monetization": True,
            "never_infer_revenue_from_views_or_engagement": True,
            "never_claim_causality_without_qualified_evidence": True,
            "never_guarantee_returns_or_manipulate_market_behavior": True,
            "never_publish_filler": True,
        },
        "next_cycle": {
            "action": action,
            "instruction": (
                "Proceed through the existing freeze, opportunity, editorial, visual, production and publication gates."
                if action == "PUBLISH_STRONG_OPPORTUNITY" else
                "Continue research/diversification. Waiting is correct when evidence or story quality is insufficient."
            ),
        },
        "guardrails": [
            "factual_accuracy",
            "originality",
            "verified_market_data",
            "authoritative_asset_lock",
            "no_fake_engagement",
            "no_guaranteed_returns",
            "no_market_manipulation",
            "no_revenue_inference",
            "no_causal_overclaim",
            "no_story_forcing",
        ],
    }

    for path in (OUT, BRIEF, REPORT):
        path.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(strategy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    BRIEF.write_text(json.dumps({
        "version": "9.1",
        "generated_at": now,
        "decision": action,
        "primary_asset": symbol,
        "story_lane": lane,
        "market_regime": regime,
        "experiment": exp,
        "monetization_feedback": monetization_signal,
        "directive": strategy["publisher_directive"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(strategy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Persist only a strategy overlay. Existing authoritative opportunity data
    # remains owned by the freeze/contract pipeline.
    memory["creator_9_0"] = strategy
    overlay = memory.get("learning_overlay") if isinstance(memory.get("learning_overlay"), dict) else {}
    overlay["autonomous_brain"] = {
        "version": "9.1",
        "action": action,
        "confidence": confidence,
        "primary_asset": symbol,
        "story_lane": lane,
        "market_regime": regime,
        "instruction": strategy["next_cycle"]["instruction"],
        "updated_at": now,
        "hard_constraints": strategy["guardrails"],
    }
    memory["learning_overlay"] = overlay
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "OK",
        "version": "9.1",
        "action": action,
        "confidence": confidence,
        "primary_asset": symbol,
        "story_lane": lane,
        "market_regime": regime,
        "experiment_id": exp["experiment_id"],
        "monetization_decision": monetization.get("decision"),
        "observation_sample": sample,
        "promotion_allowed": promotion,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
