import unittest
from nic_creator_volume_policy import recommend_volume_stage


class CreatorVolumePolicyTests(unittest.TestCase):
    def test_missing_evidence_stays_draft_only(self):
        result = recommend_volume_stage({})
        self.assertEqual(result["stage"], "DRAFT_ONLY")
        self.assertEqual(result["recommended_posts_per_day"], 0)
        self.assertFalse(result["publisher_authorized"])

    def test_critical_error_blocks_scale(self):
        result = recommend_volume_stage({"reviewed_drafts": 40, "quality_pass_rate": .99, "critical_errors": 1, "duplicate_rate": 0, "chart_match_rate": 1, "source_citation_rate": 1, "consecutive_healthy_cycles": 20})
        self.assertEqual(result["stage"], "DRAFT_ONLY")
        self.assertIn("zero_critical_errors", result["missing_requirements"])

    def test_quality_gates_only_make_one_post_pilot_eligible(self):
        result = recommend_volume_stage({"reviewed_drafts": 30, "quality_pass_rate": .93, "critical_errors": 0, "duplicate_rate": .02, "chart_match_rate": .99, "source_citation_rate": .97, "consecutive_healthy_cycles": 8})
        self.assertEqual(result["stage"], "ELIGIBLE_FOR_1_PER_DAY_PILOT")
        self.assertEqual(result["recommended_posts_per_day"], 1)
        self.assertFalse(result["publisher_authorized"])

    def test_seven_day_pilot_can_recommend_two_per_day(self):
        result = recommend_volume_stage({"reviewed_drafts": 30, "quality_pass_rate": .96, "critical_errors": 0, "duplicate_rate": .01, "chart_match_rate": .99, "source_citation_rate": .98, "consecutive_healthy_cycles": 12, "verified_pilot_days": 7, "verified_pilot_posts": 7, "pilot_quality_pass_rate": .93, "substantiated_quality_complaints": 0})
        self.assertEqual(result["stage"], "ELIGIBLE_FOR_2_PER_DAY_PILOT")
        self.assertEqual(result["recommended_posts_per_day"], 2)
        self.assertFalse(result["publisher_authorized"])

    def test_three_per_day_requires_fourteen_day_pilot(self):
        result = recommend_volume_stage({"reviewed_drafts": 40, "quality_pass_rate": .97, "critical_errors": 0, "duplicate_rate": .01, "chart_match_rate": 1, "source_citation_rate": .99, "consecutive_healthy_cycles": 20, "verified_pilot_days": 14, "verified_pilot_posts": 20, "pilot_quality_pass_rate": .96, "substantiated_quality_complaints": 0})
        self.assertEqual(result["stage"], "ELIGIBLE_FOR_3_PER_DAY_CEILING")
        self.assertEqual(result["recommended_posts_per_day"], 3)
        self.assertFalse(result["publisher_authorized"])
        self.assertFalse(result["revenue_used_for_decision"])


if __name__ == "__main__":
    unittest.main()
