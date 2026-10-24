"""Regression tests for the production creator-strategy runtime."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import creator_strategy_runtime as runtime


class CreatorStrategyRuntimeTests(unittest.TestCase):
    def test_playbook_load_records_hash_and_fit_based_strategy(self):
        playbook = {"schema_version": 1, "generation_policy": {"principle": "mechanisms, not wording"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "playbook.json"
            path.write_text(json.dumps(playbook), encoding="utf-8")
            with patch.object(runtime, "PLAYBOOK_PATH", path):
                context = {"preflight": {"selected_opportunity": {"category": "news"}, "script_director_4": {}}}
                got = runtime.prepare_context(context)
        metadata = got["creator_strategy_runtime"]
        self.assertEqual(metadata["status"], "LOADED")
        self.assertEqual(metadata["strategy_id"], "catalyst_context_and_counterpoint")
        self.assertEqual(len(metadata["playbook_sha256"]), 64)
        self.assertEqual(metadata["reward_learning_claim"], "NOT_CLAIMED")

    def test_generated_post_records_strategy_provenance(self):
        context = {"creator_strategy_runtime": {
            "strategy_id": "evidence_led_research",
            "playbook_sha256": "a" * 64,
            "playbook_schema_version": 1,
        }}
        post = "A genuinely new thesis with enough current evidence for readers to evaluate.\n\nThe counterpoint remains meaningful and can invalidate the thesis.\n\nWhat evidence would change your view?"
        with patch.object(runtime, "_recent_openings", return_value=set()):
            result = runtime.annotate_and_validate({"draft": {"text": post}}, context)
        self.assertEqual(result["draft"]["creator_strategy_id"], "evidence_led_research")
        self.assertEqual(result["creator_strategy_quality_gate"]["status"], "PASSED")
        self.assertEqual(result["draft"]["creator_strategy_version"], 1)

    def test_repeated_opening_is_rejected(self):
        post = "A repeated opening that appeared in the recent publication history. More evidence follows here."
        context = {"creator_strategy_runtime": {
            "strategy_id": "asset_specific_research_edge",
            "playbook_sha256": "b" * 64,
            "playbook_schema_version": 1,
        }}
        with patch.object(runtime, "_recent_openings", return_value={runtime._first_sentence(post)}):
            with self.assertRaisesRegex(RuntimeError, "repeated opening"):
                runtime.annotate_and_validate({"draft": {"text": post}}, context)

    def test_missing_playbook_fails_closed(self):
        with patch.object(runtime, "PLAYBOOK_PATH", Path("/path/that/does/not/exist.json")):
            with self.assertRaisesRegex(RuntimeError, "playbook missing or invalid"):
                runtime.prepare_context({})


if __name__ == "__main__":
    unittest.main()
