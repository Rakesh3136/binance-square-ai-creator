import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_problem_discovery_desk import build, cluster_problems


class ProblemDiscoveryTests(unittest.TestCase):
    def test_empty_input_never_invents_a_company_idea(self):
        result = build([])
        self.assertEqual(result["status"], "NEEDS_EVIDENCE")
        self.assertEqual(result["opportunities"], [])
        self.assertIn("don't yet have enough", result["conversation_opening"])

    def test_repeated_pain_across_independent_sources_becomes_validation_candidate(self):
        rows = [
            {"problem_cluster": "slow payout reporting", "problem_statement": "Creators cannot reconcile payouts quickly", "source_url": "https://one.example.org/a", "source_name": "Source One", "affected_user": "creators", "impact": "hours spent weekly"},
            {"problem_cluster": "slow payout reporting", "problem_statement": "Creators cannot reconcile payouts quickly", "source_url": "https://two.example.net/b", "source_name": "Source Two", "affected_user": "creators", "impact": "lost time"},
            {"problem_cluster": "slow payout reporting", "problem_statement": "Creators cannot reconcile payouts quickly", "source_url": "https://three.example.com/c", "source_name": "Source Three", "affected_user": "small creators", "impact": "missed invoices"},
            {"problem_cluster": "slow payout reporting", "problem_statement": "Creators cannot reconcile payouts quickly", "source_url": "https://four.example.io/d", "source_name": "Source Four", "affected_user": "agencies", "impact": "manual spreadsheets"},
        ]
        result = build(rows)
        self.assertEqual(result["status"], "EVIDENCE_READY_FOR_FOUNDER_DISCUSSION")
        self.assertEqual(result["opportunities"][0]["status"], "VALIDATION_CANDIDATE")
        self.assertEqual(result["opportunities"][0]["independent_source_domains"], 4)
        self.assertTrue(result["next_question"])

    def test_missing_source_or_impact_is_excluded_from_validation(self):
        rows = [
            {"problem_statement": "A real problem statement long enough", "source_url": "https://one.example.org/a", "source_name": "One"},
            {"problem_statement": "A real problem statement long enough", "source_url": "https://two.example.org/a", "source_name": "Two"},
        ]
        self.assertEqual(cluster_problems(rows), [])


if __name__ == "__main__":
    unittest.main()
