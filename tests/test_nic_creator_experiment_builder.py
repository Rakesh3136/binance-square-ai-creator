import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_creator_experiment_builder import build_experiment_results


def plan():
    return {"current_experiment": {"experiment_id": "exp-1", "control_value": "__baseline__", "treatment_value": "data_driven_breakdown"}}


def attribution(pid, arm):
    return {"post_id": pid, "experiment_id": "exp-1", "experiment_arm": arm,
            "experiment_application_status": "APPLIED"}


def performance(pid):
    return {"post_id": pid, "metrics_verified": True, "metrics": {"views": 100, "likes": 5, "comments": 2, "shares": 1, "quotes": 0}}


def reward(pid):
    return {"event_id": "r-" + pid, "post_id": pid, "verified": True, "reward_status": "PAID_VERIFIED",
            "currency": "USDC", "reward_amount_usdc": 0.25,
            "observed_at": "2026-10-01T10:00:00+00:00", "verified_at": "2026-10-01T10:05:00+00:00",
            "evidence_refs": [{"source_id": "receipt-" + pid, "sha256": "a" * 64, "observed_at": "2026-10-01T10:00:00+00:00"}]}


class CreatorExperimentBuilderTests(unittest.TestCase):
    def test_joins_exact_post_id_and_arm(self):
        report = build_experiment_results(
            [attribution("123456789", "__baseline__"), attribution("123456790", "data_driven_breakdown")],
            [performance("123456789"), performance("123456790")],
            [reward("123456789"), reward("123456790")], plan())
        exp = report["experiments"][0]
        self.assertEqual(exp["control"]["post_ids"], ["123456789"])
        self.assertEqual(exp["candidate"]["post_ids"], ["123456790"])
        self.assertEqual(exp["control"]["verified_reward_post_count"], 1)
        self.assertEqual(exp["candidate"]["verified_reward_amount_usdc"], 0.25)

    def test_does_not_join_by_symbol_or_missing_experiment_id(self):
        row = attribution("123456789", "__baseline__")
        row["experiment_id"] = ""
        report = build_experiment_results([row], [performance("123456789")], [], plan())
        self.assertEqual(report["status"], "NO_EXPERIMENT_ATTRIBUTION")
        self.assertEqual(report["experiments"][0]["control"]["post_count"], 0)

    def test_assignment_without_writer_confirmation_is_excluded(self):
        row = attribution("123456789", "__baseline__")
        row.pop("experiment_application_status")
        report = build_experiment_results([row], [performance("123456789")], [reward("123456789")], plan())
        arm = report["experiments"][0]["control"]
        self.assertEqual(arm["post_count"], 0)
        self.assertEqual(arm["verified_reward_post_count"], 0)
        self.assertEqual(report["source_counts"]["rejected_attribution_reasons"]["experiment_application_not_confirmed"], 1)

    def test_explicit_not_applied_treatment_is_excluded(self):
        row = attribution("123456789", "data_driven_breakdown")
        row["experiment_application_status"] = "NOT_APPLIED"
        report = build_experiment_results([row], [performance("123456789")], [reward("123456789")], plan())
        self.assertEqual(report["experiments"][0]["candidate"]["post_count"], 0)
        self.assertEqual(report["experiments"][0]["candidate"]["verified_reward_post_count"], 0)

    def test_unverified_metrics_are_excluded(self):
        perf = performance("123456789")
        perf["metrics_verified"] = False
        report = build_experiment_results([attribution("123456789", "__baseline__")], [perf], [], plan())
        self.assertEqual(report["experiments"][0]["control"]["post_count"], 0)

    def test_unattributed_reward_does_not_count(self):
        report = build_experiment_results([attribution("123456789", "__baseline__")],
            [performance("123456789")], [reward("123456790")], plan())
        arm = report["experiments"][0]["control"]
        self.assertEqual(arm["verified_reward_post_count"], 0)
        self.assertIsNone(arm["verified_reward_amount_usdc"])
        self.assertGreater(report["source_counts"]["rejected_reward_reasons"].get("verified_reward_not_joined_to_experiment_post", 0), 0)

    def test_duplicate_attribution_does_not_inflate_metrics(self):
        row = attribution("123456789", "__baseline__")
        report = build_experiment_results([row, dict(row)], [performance("123456789")], [], plan())
        arm = report["experiments"][0]["control"]
        self.assertEqual(arm["post_count"], 1)
        self.assertEqual(arm["views"], 100)

    def test_conflicting_arm_assignment_is_excluded(self):
        report = build_experiment_results(
            [attribution("123456789", "__baseline__"), attribution("123456789", "data_driven_breakdown")],
            [performance("123456789")], [], plan())
        exp = report["experiments"][0]
        self.assertEqual(exp["control"]["post_count"], 0)
        self.assertEqual(exp["candidate"]["post_count"], 0)
        self.assertEqual(report["source_counts"]["conflicting_arm_assignment_posts"], 1)

    def test_duplicate_reward_event_id_counts_once(self):
        event = reward("123456789")
        report = build_experiment_results([attribution("123456789", "__baseline__")],
            [performance("123456789")], [event, dict(event)], plan())
        arm = report["experiments"][0]["control"]
        self.assertEqual(arm["verified_reward_post_count"], 1)
        self.assertEqual(arm["verified_reward_amount_usdc"], 0.25)
        self.assertEqual(report["source_counts"]["rejected_reward_reasons"]["duplicate_reward_event_id"], 1)

    def test_invalid_reward_does_not_count(self):
        bad = reward("123456789")
        bad["verified"] = False
        report = build_experiment_results([attribution("123456789", "__baseline__")],
            [performance("123456789")], [bad], plan())
        self.assertEqual(report["experiments"][0]["control"]["verified_reward_post_count"], 0)


if __name__ == "__main__":
    unittest.main()
