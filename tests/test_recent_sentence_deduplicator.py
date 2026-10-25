import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import src.recent_sentence_deduplicator as dedup

class RecentSentenceDeduplicatorTests(unittest.TestCase):
    def test_replaces_exact_repeated_generic_sentences_and_preserves_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repeated = "That keeps the read falsifiable the next measurable reaction either supports the structure or weakens it."
            second = "The available evidence supports a scenario to test not certainty about the next candle."
            log = root / "publication_log.jsonl"
            log.write_text(json.dumps({"text": repeated + " " + second}) + "\n", encoding="utf-8")
            report = root / "draft.json"
            report.write_text(json.dumps({"draft": {"symbol": "EPIC", "post": repeated + " " + second + " What evidence should readers watch next?"}}), encoding="utf-8")
            out = root / "dedup.json"
            with patch.object(dedup, "LOG", log), patch.object(dedup, "OUT", out), patch.object(dedup, "REPORT_DIR", root), patch.dict("os.environ", {"DRAFT_PATH": str(report)}):
                rc = dedup.main()
            self.assertEqual(rc, 0)
            updated = json.loads(report.read_text(encoding="utf-8"))["draft"]["post"]
            self.assertEqual(updated.count("?"), 1)
            self.assertIn("What evidence should readers watch next?", updated)
            self.assertNotIn(repeated.rstrip("."), updated)
            self.assertNotIn(second.rstrip("."), updated)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["factual_sentences_rewritten"], 0)

    def test_does_not_rewrite_repeated_fact_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repeated = "EPIC rose 12.5% after the update, according to the report."
            log = root / "publication_log.jsonl"
            log.write_text(json.dumps({"text": repeated}) + "\n", encoding="utf-8")
            report = root / "draft.json"
            original = repeated + " What evidence should readers watch next?"
            report.write_text(json.dumps({"draft": {"symbol": "EPIC", "post": original}}), encoding="utf-8")
            out = root / "dedup.json"
            with patch.object(dedup, "LOG", log), patch.object(dedup, "OUT", out), patch.object(dedup, "REPORT_DIR", root), patch.dict("os.environ", {"DRAFT_PATH": str(report)}):
                rc = dedup.main()
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["draft"]["post"], original)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["changed"], 0)
            self.assertEqual(result["replacements"][0]["status"], "preserved_factual_repeat")

if __name__ == "__main__":
    unittest.main()
