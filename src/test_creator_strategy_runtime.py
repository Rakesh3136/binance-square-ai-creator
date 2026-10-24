"""Regression tests for the NIC creator-strategy runtime."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import creator_strategy_runtime as runtime


class CreatorStrategyRuntimeTests(unittest.TestCase):
    def test_prepare_context_records_playbook_version_and_fit_strategy(self):
        playbook = {"schema_version": 1, "generation_policy": {"principle": "mechanisms, not wording"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "playbook.json"
            path.write_text(json.dumps(playbook), encoding="utf-8")
            with patch.object(runtime, "PLAYBOOK_PATH", path):
                ctx = {
                    "preflight": {
                        "selected_opportunity": {"category": "news"},
                        "script_director_4": {},
                    }
                }
                got = runtime.prepare_context(ctx)
        self.assertEqual(got["creator_strategy_runtime"]["status"], "LOADED")
        self.assertEqual(got["creator_strategy_runtime"]["strategy_id"], "catalyst_context_and_counterpoint")
        self.assertEqual(len(got["creator_strategy_runtime"]["playbook_sha256"]), 64)
        self.assertEqual(got["creator_strategy_runtime"]["reward_learning_claim"], "NOT_CLAIMED")

    def test_post_records_strategy_provenance(self):
        ctx = {"creator_strategy_runtime": {
            "strategy_id": "evidence_led_research",
            "playbook_sha256": "a" * 64,
            "playbook_schema_version": 1,
        }}
        with patch.object(runtime, "_recent_openings", return_value=set()):
            result = runtime.annotate_and_validate(
                {"draft": {"text": "A genuinely new thesis with current evidence."}}, ctx
            )
        self.assertEqual(result["draft"]["creator_strategy_id"], "evidence_led_research")
        self.assertEqual(result["creator_strategy_quality_gate"]["status"], "PASSED")

    def test_repeated_opening_is_rejected(self):
        text = "A repeated opening that appeared in the recent publication history."
        ctx = {"creator_strategy_runtime": {
            "strategy_id": "asset_specific_research_edge",
            "playbook_sha256": "b" * 64,
            "playbook_schema_version": 1,
        }}
        with patch.object(runtime, "_recent_openings", return_value={runtime._first_sentence(text)}):
            with self.assertRaisesRegex(RuntimeError, "repeated opening"):
                runtime.annotate_and_validate({"draft": {"text": text}}, ctx)


if __name__ == "__main__":
    unittest.main()
