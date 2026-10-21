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



    def test_owner_reported_reward_learning_is_explicitly_separate_from_verified_revenue(self):
        helper = (ROOT / "src" / "nic_owner_reported_rewards.py").read_text(encoding="utf-8")
        lab = (ROOT / "src" / "nic_revenue_pattern_lab.py").read_text(encoding="utf-8")
        director = (ROOT / "src" / "revenue_content_director.py").read_text(encoding="utf-8")
        self.assertIn("OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED", helper + lab + director)
        self.assertIn("analytics/wte_owner_reported_reward_events.jsonl", helper + lab)
        self.assertIn("owner_reported_revenue_total_usdc", director)
        self.assertIn("revenue_requires_exact_post_id_and_hashed_timestamped_evidence", director)
        self.assertIn("is_verified_reward_event(event)", director)

    def test_owner_reported_reward_learning_does_not_change_verified_reward_gate(self):
        reward = (ROOT / "src" / "nic_reward_evidence.py").read_text(encoding="utf-8")
        director = (ROOT / "src" / "revenue_content_director.py").read_text(encoding="utf-8")
        self.assertIn("def is_verified_reward_event", reward)
        self.assertIn("accepted_verified_reward_events", director)
        self.assertIn("owner_reported_revenue_is_separate_and_not_independently_verified", director)


    def test_7_and_14_day_creator_research_is_built_before_editorial_preflight(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        benchmark = "run_component run_creator_intelligence python src/run_creator_intelligence.py"
        learning = "run_component nic_square_earnings_learning python src/nic_square_earnings_learning.py"
        preflight = "run_component editorial_preflight python src/editorial_preflight.py"
        self.assertIn(benchmark, text)
        self.assertIn(learning, text)
        self.assertIn(preflight, text)
        self.assertLess(text.index(benchmark), text.index(learning))
        self.assertLess(text.index(learning), text.index(preflight))
        learning_source = (ROOT / "src/nic_square_earnings_learning.py").read_text(encoding="utf-8")
        self.assertIn('"window_days": [7, 14]', learning_source)
        self.assertIn('"automatic_posting_enabled": bool(load_json(ROOT / "nic_publication_policy.json"', learning_source)
        self.assertIn('"format_reward_map"', learning_source)
        self.assertIn('"creator_format_strategy"', learning_source)

    def test_creator_learning_outputs_are_validated_ignored_for_push_trigger_and_persisted(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        ignored = text.split("paths-ignore:", 1)[1].split("  schedule:", 1)[0]
        outputs = (
            "data/live/nic_square_earnings_learning.json",
            "data/intelligence/nic_square_earnings_learning_report.json",
            "analytics/nic_square_earnings_learning_memory.json",
            "analytics/square_creator_benchmark_history.jsonl",
        )
        for output in outputs:
            with self.subTest(output=output):
                self.assertIn(output, ignored)
                self.assertGreaterEqual(text.count(output), 3)

if __name__ == "__main__":
    unittest.main()
