import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_experiment_assignment import assign_experiment, mark_treatment_applied


class ExperimentAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"status": "ACTIVE", "current_experiment": {
            "status": "ACTIVE", "experiment_id": "exp-test", "primary_variable": "experiment_format",
            "control_value": "__baseline__", "treatment_value": "data_driven_breakdown"}}

    def test_assignment_is_deterministic_for_cycle(self):
        first = assign_experiment(self.plan, "run-123")
        second = assign_experiment(self.plan, "run-123")
        self.assertEqual(first, second)
        self.assertIn(first["experiment_arm"], {"control", "candidate"})
        self.assertFalse(first["publication_authorized"])

    def test_different_cycles_can_be_assigned_independently(self):
        values = {assign_experiment(self.plan, f"run-{i}")["experiment_arm"] for i in range(40)}
        self.assertEqual(values, {"control", "candidate"})

    def test_inactive_plan_fails_closed(self):
        self.plan["current_experiment"]["status"] = "PAUSED"
        self.assertFalse(assign_experiment(self.plan, "run-123")["assigned"])

    def test_missing_cycle_does_not_fabricate_assignment(self):
        result = assign_experiment(self.plan, "")
        self.assertEqual(result["status"], "NO_STABLE_CYCLE_ID")
        self.assertFalse(result["assigned"])

    def test_application_requires_explicit_writer_confirmation(self):
        assigned = assign_experiment(self.plan, "run-123")
        self.assertEqual(assigned["application_status"], "PENDING_WRITER_CONFIRMATION")
        self.assertEqual(mark_treatment_applied(assigned, False)["application_status"], "NOT_APPLIED")


if __name__ == "__main__":
    unittest.main()
