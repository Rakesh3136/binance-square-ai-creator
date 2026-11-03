import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import nic_native_writer
from src.bounded_editorial_improvement import generate_and_select


class NativeWriterStrategyDiversityTests(unittest.TestCase):
    def test_four_research_strategies_change_the_evidence_angle_and_avoid_reused_close(self):
        repeated_close = (
            "That keeps the read falsifiable: the next measurable reaction "
            "either supports the structure or weakens it."
        )
        context = {
            "preflight": {
                "selected_opportunity": {
                    "symbol": "HOT",
                    "category": "research_insight",
                    "story_type": "research_edge",
                },
                "script_director_4": {"story_type": "research_edge"},
            },
            "publication": {
                "symbol": "HOT",
                "category": "research_insight",
                "timing_state": "EXHAUSTED",
                "research_observation": {
                    "missing_evidence": ["external_news_corroboration", "holder_concentration"],
                    "news_count": 0,
                    "official_evidence_count": 0,
                },
            },
            "market": {
                "top_content_signals": [{
                    "symbol": "HOT",
                    "last_price": 0.42,
                    "price_change_percent": 18.5,
                    "quote_volume_usdt": 4200000,
                    "intraday_range_percent": 21.0,
                    "candles_1h": [
                        [0, 0.38, 0.44, 0.36, 0.42, 1000],
                        [1, 0.42, 0.43, 0.39, 0.41, 900],
                    ],
                }],
            },
            "recent_publication_texts": [repeated_close],
        }
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "publication_log.jsonl"
            log.write_text(json.dumps({"text": repeated_close}) + "\n", encoding="utf-8")
            with patch.object(nic_native_writer, "RECENT_LOG", log):
                selected = generate_and_select(
                    context,
                    lambda candidate_context: nic_native_writer.build(candidate_context),
                    max_candidates=4,
                )

        reports = selected["editorial_iteration"]["candidates"]
        self.assertEqual(len(reports), 4)
        self.assertEqual(selected["editorial_iteration"]["eligible_candidates"], 4)
        posts = [
            # Rebuild each strategy from the same frozen evidence to inspect
            # distinct outputs; generation remains deterministic and bounded.
            nic_native_writer.build({
                **context,
                "iteration_seed": index,
                "iteration_strategy_id": strategy,
            })["draft"]["post"]
            for index, strategy in enumerate((
                "asset_specific_research_edge",
                "evidence_led_research",
                "structure_and_confirmation",
                "participation_and_relative_strength",
            ))
        ]
        self.assertEqual(len(set(posts)), 4)
        self.assertTrue(all(post.count("?") == 1 for post in posts))
        self.assertTrue(all(280 <= len(post) <= 700 for post in posts))
        self.assertTrue(all(repeated_close not in post for post in posts))
        self.assertTrue(any("Evidence first:" in post for post in posts))
        self.assertTrue(any("observed 1H range" in post for post in posts))
        self.assertTrue(any("participation record" in post for post in posts))


if __name__ == "__main__":
    unittest.main()
