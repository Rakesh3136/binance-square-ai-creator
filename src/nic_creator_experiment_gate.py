"""Evidence gate for NIC creator experiments.

Public engagement can generate hypotheses, but cannot prove monetization.
Promotion is deliberately conservative and never enables publication.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analytics" / "creator_experiment_results.json"
OUTPUT = ROOT / "data" / "intelligence" / "creator_experiment_gate.json"
MIN_POSTS_PER_ARM = 5


def _positive_int(value):
    try:
        n = int(value)
        return n if n >= 0 else 0
    except (TypeError, ValueError):
        return 0


def _rate(arm, numerator, denominator):
    try:
        den = float(arm.get(denominator, 0) or 0)
        num = float(arm.get(numerator, 0) or 0)
        if den <= 0 or num < 0:
            return None
        return num / den
    except (TypeError, ValueError):
        return None


def evaluate_experiment(experiment):
    """Return an auditable status; missing or weak evidence fails closed."""
    if not isinstance(experiment, dict):
        return {"status": "BLOCKED_INVALID_EXPERIMENT", "reasons": ["experiment_not_object"]}

    control = experiment.get("control") if isinstance(experiment.get("control"), dict) else {}
    candidate = experiment.get("candidate") if isinstance(experiment.get("candidate"), dict) else {}
    control_n = _positive_int(control.get("post_count"))
    candidate_n = _positive_int(candidate.get("post_count"))
    reasons = []

    if not experiment.get("experiment_id"):
        reasons.append("missing_experiment_id")
    if control_n < MIN_POSTS_PER_ARM:
        reasons.append("insufficient_control_posts")
    if candidate_n < MIN_POSTS_PER_ARM:
        reasons.append("insufficient_candidate_posts")

    control_engagement = _rate(control, "engagements", "views")
    candidate_engagement = _rate(candidate, "engagements", "views")
    if control_engagement is None or candidate_engagement is None:
        reasons.append("missing_or_invalid_engagement_denominator")

    # Only exact-post verified reward events count. A free-form revenue field,
    # public engagement, or a boolean alone is not evidence.
    control_rewards = _positive_int(control.get("verified_reward_post_count"))
    candidate_rewards = _positive_int(candidate.get("verified_reward_post_count"))
    control_reward_amount = control.get("verified_reward_amount_usdc")
    candidate_reward_amount = candidate.get("verified_reward_amount_usdc")
    control_reward_proof = bool(control.get("reward_evidence_refs")) and control_rewards > 0
    candidate_reward_proof = bool(candidate.get("reward_evidence_refs")) and candidate_rewards > 0

    engagement_delta = None
    if control_engagement is not None and candidate_engagement is not None:
        engagement_delta = candidate_engagement - control_engagement

    if reasons:
        status = "COLLECTING_MORE_EVIDENCE"
    elif not control_reward_proof or not candidate_reward_proof:
        status = "ENGAGEMENT_ONLY_NOT_MONETIZATION_PROVEN"
        reasons.append("both_arms_need_exact_post_verified_reward_evidence")
    else:
        # Even when rewards are present, this report only recommends human review;
        # it does not automatically promote or publish a content strategy.
        status = "ELIGIBLE_FOR_HUMAN_REVIEW"
    return {
        "experiment_id": str(experiment.get("experiment_id") or ""),
        "status": status,
        "reasons": reasons,
        "control_post_count": control_n,
        "candidate_post_count": candidate_n,
        "control_engagement_rate": control_engagement,
        "candidate_engagement_rate": candidate_engagement,
        "candidate_minus_control_engagement_rate": engagement_delta,
        "control_verified_reward_post_count": control_rewards,
        "candidate_verified_reward_post_count": candidate_rewards,
        "control_verified_reward_amount_usdc": control_reward_amount if control_reward_proof else None,
        "candidate_verified_reward_amount_usdc": candidate_reward_amount if candidate_reward_proof else None,
        "publication_authorized": False,
        "strategy_auto_promoted": False,
    }


def main():
    if INPUT.exists():
        try:
            payload = json.loads(INPUT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
    else:
        payload = None

    experiments = payload.get("experiments", []) if isinstance(payload, dict) else []
    results = [evaluate_experiment(x) for x in experiments if isinstance(x, dict)]
    report = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if isinstance(payload, dict) else "INPUT_MISSING_OR_INVALID",
        "input_path": str(INPUT.relative_to(ROOT)),
        "experiment_count": len(results),
        "results": results,
        "publication_authorized": False,
        "strategy_auto_promoted": False,
        "note": "Engagement is a hypothesis signal, not earnings proof. Promotion requires exact-post verified rewards and human review.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "experiment_count": len(results), "output": str(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
