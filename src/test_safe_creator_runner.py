"""Tests that originality failures never trigger generic fallback prose."""
import unittest
import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch
import safe_creator_runner


class SafeCreatorRunnerTests(unittest.TestCase):
    def test_no_original_candidate_blocks_without_running_emergency_fallback(self):
        message = (
            "NIC bounded editorial improvement found no candidate passing its local rubric; "
            "diagnostics={\"status\":\"NO_ELIGIBLE_NATIVE_CANDIDATE\","
            "\"issues\":[\"repeats_recent_published_sentence\"]}"
        )
        output = io.StringIO()
        with patch.object(safe_creator_runner, "run_creator", side_effect=RuntimeError(message)), \
             patch.object(safe_creator_runner, "emergency_verified_draft") as fallback, \
             patch.object(safe_creator_runner, "save_status") as save, \
             redirect_stdout(output):
            result = safe_creator_runner.main()
        self.assertEqual(result, 1)
        fallback.assert_not_called()
        self.assertEqual(save.call_args.args[0], "AI_BLOCKED_NO_ORIGINAL_DRAFT")
        self.assertEqual(save.call_args.kwargs["fallback_status"], "NOT_RUN_TO_PROTECT_ORIGINALITY")
        emitted = json.loads(output.getvalue())
        self.assertEqual(emitted["diagnostic"], message)
        self.assertFalse(emitted["publication_allowed"])

    def test_similarity_failure_markers_are_detected(self):
        self.assertTrue(safe_creator_runner.is_no_original_draft_failure("final_gate_originality_conflict"))
        self.assertTrue(safe_creator_runner.is_no_original_draft_failure("near_duplicate_of_recent_publication"))
        self.assertFalse(safe_creator_runner.is_no_original_draft_failure("temporary network timeout"))


if __name__ == "__main__":
    unittest.main()
