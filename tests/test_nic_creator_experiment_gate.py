import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "src" / "nic_creator_experiment_gate.py"
spec = importlib.util.spec_from_file_location("nic_creator_experiment_gate", MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def arm(posts=6, views=1000, engagements=50, reward_count=0, reward_amount=None, refs=None):
    return {
        "post_count": posts,
        "views": views,
        "engagements": engagements,
        "verified_reward_post_count": reward_count,
        "verified_reward_amount_usdc": reward_amount,
        "reward_evidence_refs": refs or [],
    }


class CreatorExperimentGateTests(unittest.TestCase):
    def test_engagement_lift_without_rewards_is_not_monetization_proof(self):
        result = gate.evaluate_experiment({
            "experiment_id": "test-engagement-only",
            "control": arm(engagements=20),
            "candidate": arm(engagements=100),
        })
        self.assertEqual(result["status"], "ENGAGEMENT_ONLY_NOT_MONETIZATION_PROVEN")
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["strategy_auto_promoted"])

    def test_small_sample_stays_collecting(self):
        result = gate.evaluate_experiment({
            "experiment_id": "small",
            "control": arm(posts=4),
            "candidate": arm(posts=5),
        })
        self.assertEqual(result["status"], "COLLECTING_MORE_EVIDENCE")
        self.assertIn("insufficient_control_posts", result["reasons"])

    def test_reward_proof_in_both_arms_only_allows_human_review(self):
        result = gate.evaluate_experiment({
            "experiment_id": "review-only",
            "control": arm(reward_count=1, reward_amount=0.2, refs=["sha256:control-proof"]),
            "candidate": arm(reward_count=2, reward_amount=0.7, refs=["sha256:candidate-proof"]),
        })
        self.assertEqual(result["status"], "ELIGIBLE_FOR_HUMAN_REVIEW")
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["strategy_auto_promoted"])

    def test_zero_reward_amount_does_not_count_as_verified_revenue(self):
        result = gate.evaluate_experiment({
            "experiment_id": "zero-reward",
            "control": arm(reward_count=1, reward_amount=0, refs=["sha256:control-proof"]),
            "candidate": arm(reward_count=1, reward_amount=0.7, refs=["sha256:candidate-proof"]),
        })
        self.assertEqual(result["status"], "ENGAGEMENT_ONLY_NOT_MONETIZATION_PROVEN")
        self.assertIsNone(result["control_verified_reward_amount_usdc"])

    def test_missing_experiment_id_fails_closed(self):
        result = gate.evaluate_experiment({
            "control": arm(),
            "candidate": arm(),
        })
        self.assertEqual(result["status"], "COLLECTING_MORE_EVIDENCE")
        self.assertIn("missing_experiment_id", result["reasons"])

    def test_engagement_rate_is_not_inflated_by_invalid_denominator(self):
        result = gate.evaluate_experiment({
            "experiment_id": "zero-views",
            "control": arm(views=0),
            "candidate": arm(),
        })
        self.assertEqual(result["status"], "COLLECTING_MORE_EVIDENCE")
        self.assertIsNone(result["control_engagement_rate"])


if __name__ == "__main__":
    unittest.main()
