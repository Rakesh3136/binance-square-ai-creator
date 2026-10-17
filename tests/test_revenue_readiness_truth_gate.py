import unittest

from src.revenue_content_director import readiness_status


class RevenueReadinessTruthGateTests(unittest.TestCase):
    def test_observations_without_verified_reward_do_not_claim_ready(self):
        self.assertEqual(
            readiness_status(0, [{"samples": 777, "verified_revenue_observations": 0}]),
            "COLLECTING_VERIFIED_REWARD_EVIDENCE",
        )

    def test_no_rows_and_no_reward_evidence_stays_blocked(self):
        self.assertEqual(readiness_status(0, []), "COLLECTING_VERIFIED_REWARD_EVIDENCE")

    def test_verified_reward_with_attributed_rows_can_be_ready(self):
        self.assertEqual(readiness_status(1, [{"samples": 3}]), "READY")

    def test_reward_without_attributed_rows_waits_for_attribution(self):
        self.assertEqual(readiness_status(1, []), "COLLECTING_ATTRIBUTED_PERFORMANCE_DATA")


if __name__ == "__main__":
    unittest.main()
