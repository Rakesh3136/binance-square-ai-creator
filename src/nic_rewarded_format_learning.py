"""Turn owner-reported rewarded posts into cautious, transferable format hypotheses.

Never expose payout amounts, post IDs, source-asset levels, URLs, or original prose
to the writer. A single owner-reported sample is exploratory, not causal proof.
"""
from __future__ import annotations

try:
    from src.nic_owner_reported_rewards import load_owner_reported_rewards
except ModuleNotFoundError:
    from nic_owner_reported_rewards import load_owner_reported_rewards


def build_owner_rewarded_format_brief(rewards: dict | None = None) -> dict:
    records = rewards if isinstance(rewards, dict) else load_owner_reported_rewards()
    examples = []
    for item in records.values():
        if not isinstance(item, dict):
            continue
        meta = item.get("content_metadata") if isinstance(item.get("content_metadata"), dict) else {}
        if not meta or not (meta.get("content_format") or meta.get("timeframe") or meta.get("setup_structure")):
            continue
        features = []
        if meta.get("timeframe"):
            features.append("state the timeframe explicitly")
        if meta.get("chart_type"):
            features.append("use a chart only when it proves the selected thesis")
        if meta.get("setup_structure"):
            features.append("explain the asset-specific structure and why it matters")
        if meta.get("confirmation_condition"):
            features.append("state what would confirm the thesis")
        if meta.get("invalidation_condition"):
            features.append("state a concrete invalidation/falsification condition")
        if meta.get("target_levels"):
            features.append("present scenario levels only when independently supported by current research")
        examples.append({
            "format_archetype": str(meta.get("content_format") or "evidence_led_setup")[:80],
            "timeframe": str(meta.get("timeframe") or "")[:20] or None,
            "chart_type": str(meta.get("chart_type") or "")[:60] or None,
            "transferable_features": features,
            "sample_count": 1,
            "confidence": "LOW_SINGLE_SAMPLE",
            "evidence_type": "OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "lesson": "A potentially useful setup format combines a clear asset-specific thesis, visible evidence, a confirmation condition, an invalidation condition, and conditional scenarios.",
            "limitations": [
                "One rewarded post does not prove that its format caused the reward.",
                "Do not copy the source asset, wording, price levels, targets, chart, or creator identity.",
                "Rebuild every claim from fresh, current, asset-specific research.",
                "Use this as an exploratory format option only when the selected story and evidence naturally support it.",
            ],
        })
    return {
        "status": "OWNER_REPORTED_FORMAT_HYPOTHESIS_AVAILABLE" if examples else "NO_OWNER_REPORTED_FORMAT_EXAMPLES",
        "examples": examples[:5],
        "writer_use": "TRANSFERABLE_STRUCTURE_ONLY",
        "not_a_verified_reward_label": True,
        "minimum_independent_samples_before_generalizing": 3,
    }
