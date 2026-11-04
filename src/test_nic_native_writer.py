"""Regression tests for NIC native writer angle and question diversity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import nic_native_writer


class NativeWriterQuestionTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "preflight": {
                "selected_opportunity": {
                    "symbol": "ICX",
                    "category": "technical_setup",
                    "trade_setup": {
                        "side": "LONG",
                        "trigger": 0.0123,
                        "invalidation": 0.0111,
                        "tp1": 0.0135,
                        "tp2": 0.0145,
                    },
                },
                "script_director_4": {
                    "primary_symbol": "ICX",
                    "story_type": "momentum_volume",
                },
            },
            "publication": {"symbol": "ICX", "category": "technical_setup", "timing_state": "ACTIVE"},
            "market": {
                "top_content_signals": [{
                    "symbol": "ICXUSDT",
                    "last_price": 0.012,
                    "quote_volume_usdt": 1230000,
                    "price_change_percent": 4.2,
                    "intraday_range_percent": 6.2,
                    "candles_1h": [
                        [0, 0.0118, 0.0124, 0.0115, 0.0120, 1],
                        [1, 0.0120, 0.0125, 0.0117, 0.0121, 1],
                    ],
                }],
            },
        }

    def test_bounded_trade_variants_use_distinct_questions_and_avoid_old_generic_cta(self):
        old_question = "What would you need to see on $ICX before you would consider this LONG scenario confirmed?"
        with tempfile.TemporaryDirectory() as temp:
            recent_log = Path(temp) / "publication_log.jsonl"
            recent_log.write_text(json.dumps({"text": old_question}) + "\n", encoding="utf-8")
            with patch.object(nic_native_writer, "RECENT_LOG", recent_log):
                results = [
                    nic_native_writer.build({**self.context, "iteration_seed": seed})
                    for seed in range(4)
                ]
        questions = [result["draft"]["discussion_question"] for result in results]
        self.assertEqual(len(set(questions)), 4)
        self.assertNotIn(old_question, questions)
        for result in results:
            self.assertEqual(result["draft"]["post"].count("?"), 1)
            self.assertIn("$ICX", result["draft"]["post"])


    def test_writer_refuses_to_reuse_cta_when_all_variants_are_recent(self):
        with tempfile.TemporaryDirectory() as temp:
            recent_log = Path(temp) / "publication_log.jsonl"
            with patch.object(nic_native_writer, "RECENT_LOG", recent_log):
                prior_questions = [
                    nic_native_writer.build({**self.context, "iteration_seed": seed})["draft"]["discussion_question"]
                    for seed in range(4)
                ]
                recent_log.write_text(
                    "".join(json.dumps({"text": question}) + "\n" for question in prior_questions),
                    encoding="utf-8",
                )
                for seed in range(4):
                    with self.assertRaisesRegex(RuntimeError, "no_fresh_reader_question_variant"):
                        nic_native_writer.build({**self.context, "iteration_seed": seed})

    def test_writer_uses_iteration_seed_to_cover_each_trade_style_once(self):
        styles = []
        for seed in range(4):
            result = nic_native_writer.build({**self.context, "iteration_seed": seed})
            styles.append(result["draft"]["hook"])
        self.assertEqual(len(set(styles)), 4)


if __name__ == "__main__":
    unittest.main()
