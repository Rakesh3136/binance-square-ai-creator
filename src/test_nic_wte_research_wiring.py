"""Regression tests for production wiring of public creator research and evidence persistence."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/autonomous-market-creator.yml"


class WteResearchWiringTests(unittest.TestCase):
    def test_profile_research_runs_before_earnings_learning(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        profile = "run_component nic_square_profile_research python src/nic_square_profile_research.py"
        learning = "run_component nic_square_earnings_learning python src/nic_square_earnings_learning.py"
        self.assertIn(profile, text)
        self.assertIn(learning, text)
        self.assertLess(text.index(profile), text.index(learning))

    def test_profile_research_outputs_are_persisted(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("data/intelligence/nic_square_profile_research.json", text)
        self.assertIn("data/intelligence/wte_leaderboard_observed.json", text)
        self.assertIn("data/intelligence/nic_autonomy_readiness.json", text)

    def test_authenticated_leaderboard_is_not_fabricated(self):
        source = (ROOT / "src/nic_square_profile_research.py").read_text(encoding="utf-8")
        self.assertIn("OBSERVED_LEADERBOARD_PATH", source)
        self.assertIn("observed_write_to_earn_leaderboard", source)
        self.assertIn("Never derive a profile URL from a display name", source)
        template = (ROOT / "data/intelligence/wte_leaderboard_observations.json").read_text(encoding="utf-8")
        self.assertIn('"entries": []', template)


if __name__ == "__main__":
    unittest.main()
