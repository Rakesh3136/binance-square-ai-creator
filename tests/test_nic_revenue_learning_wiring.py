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

    def test_publication_requires_exact_draft_authorization(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        auth = (ROOT / "src/nic_publication_authorization.py").read_text(encoding="utf-8")
        publisher = (ROOT / "src/binance_square_publisher.py").read_text(encoding="utf-8")
        self.assertIn("NIC editorial automatic-publication authorization", text)
        self.assertIn("Final NIC 21 and editorial revalidation", text)
        self.assertIn("steps.publication_authorization.outputs.authorized == 'true'", text)
        self.assertIn("trade_signal_publication_authorized", auth)
        self.assertIn("live_orders_authorized", auth)
        self.assertIn("verify_quality_authorization", publisher)


if __name__ == "__main__":
    unittest.main()
