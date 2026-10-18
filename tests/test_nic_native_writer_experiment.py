import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_native_writer import apply_experiment_format


class NativeWriterExperimentFormatTests(unittest.TestCase):
    def test_candidate_applies_data_driven_breakdown_labels(self):
        parts = ["Hook", "Observed evidence.", "Interpretation.", "Falsifier."]
        assignment = {"assigned": True, "experiment_arm": "candidate",
                      "experiment_variable": "experiment_format",
                      "experiment_treatment": "data_driven_breakdown"}
        formatted, status = apply_experiment_format(parts, assignment)
        self.assertEqual(status, "APPLIED")
        self.assertEqual(formatted[1], "Evidence observed: Observed evidence.")
        self.assertEqual(formatted[2], "Interpretation: Interpretation.")
        self.assertEqual(formatted[3], "What would change this view: Falsifier.")

    def test_control_preserves_baseline_format(self):
        parts = ["Hook", "Evidence.", "Read.", "Falsifier."]
        assignment = {"assigned": True, "experiment_arm": "control",
                      "experiment_variable": "experiment_format",
                      "experiment_treatment": "__baseline__"}
        formatted, status = apply_experiment_format(parts, assignment)
        self.assertEqual(status, "APPLIED")
        self.assertEqual(formatted, parts)

    def test_unsupported_treatment_is_not_claimed_as_applied(self):
        parts = ["Hook", "Evidence.", "Read.", "Falsifier."]
        assignment = {"assigned": True, "experiment_arm": "candidate",
                      "experiment_variable": "hook_type",
                      "experiment_treatment": "dramatic_hook"}
        formatted, status = apply_experiment_format(parts, assignment)
        self.assertEqual(status, "NOT_APPLIED")
        self.assertEqual(formatted, parts)


if __name__ == "__main__":
    unittest.main()
