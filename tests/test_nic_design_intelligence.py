import unittest

from src.nic_design_intelligence import build_design_brief, get_design_guidelines


class NICDesignIntelligenceTests(unittest.TestCase):
    def test_guidelines_define_product_surfaces_and_owner_guardrails(self):
        data = get_design_guidelines()
        self.assertEqual(data["product"], "NIC — Neural Intelligence Companion")
        self.assertIn("assistant", {item["id"] for item in data["core_surfaces"]})
        self.assertIn("accessibility review", data["preview_policy"]["required_before_approval"])
        self.assertIn("authentication", data["preview_policy"]["never_modify_without_explicit_owner_approval"])

    def test_guidelines_are_copy_safe(self):
        data = get_design_guidelines()
        data["visual_direction"]["palette"]["background"] = "#ffffff"
        self.assertNotEqual(get_design_guidelines()["visual_direction"]["palette"]["background"], "#ffffff")

    def test_design_brief_is_scoped_and_requires_approval(self):
        brief = build_design_brief("Make assistant chat easier to use one-handed", "assistant")
        self.assertEqual(brief["surface"]["id"], "assistant")
        self.assertEqual(brief["goal"], "Make assistant chat easier to use one-handed")
        self.assertTrue(brief["approval_required_before_production"])
        self.assertEqual(brief["file_write_authority"], "none")
        self.assertIn("isolated preview", brief["deliverables"])

    def test_invalid_surface_and_goal_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "design_goal_invalid"):
            build_design_brief(" ")
        with self.assertRaisesRegex(ValueError, "design_surface_invalid"):
            build_design_brief("Improve interface", "../../secrets")


if __name__ == "__main__":
    unittest.main()
