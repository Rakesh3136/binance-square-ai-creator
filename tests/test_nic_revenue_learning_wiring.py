import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/autonomous-market-creator.yml"


class RevenueLearningProductionWiringTests(unittest.TestCase):
    def test_production_runs_both_evidence_first_learning_modules(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        lab = "python src/nic_revenue_pattern_lab.py"
        director = "python src/revenue_content_director.py"
        self.assertIn(lab, text)
        self.assertIn(director, text)
        self.assertLess(text.index(lab), text.index(director))

    def test_reports_are_validated_and_persisted(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        outputs = (
            "data/live/nic_revenue_pattern_lab.json",
            "data/intelligence/nic_revenue_pattern_lab_report.json",
            "data/live/revenue_content_director.json",
            "data/intelligence/revenue_content_director_report.json",
        )
        for output in outputs:
            with self.subTest(output=output):
                self.assertIn(output, text)
                self.assertGreaterEqual(text.count(output), 3)

    def test_generated_reports_are_ignored_by_push_trigger(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        ignored = text.split("paths-ignore:", 1)[1].split("  schedule:", 1)[0]
        for output in (
            "data/live/nic_revenue_pattern_lab.json",
            "data/intelligence/nic_revenue_pattern_lab_report.json",
            "data/live/revenue_content_director.json",
            "data/intelligence/revenue_content_director_report.json",
        ):
            with self.subTest(output=output):
                self.assertIn(output, ignored)

    def test_publication_remains_hard_paused(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("NIC editorial automatic-publication authorization", text)
        self.assertIn("Extract publication and submit to Binance Square", text)
        guard = "if: " + "$" + "{{ false }}"
        self.assertGreaterEqual(text.count(guard), 2)


if __name__ == "__main__":
    unittest.main()
