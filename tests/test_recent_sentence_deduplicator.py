import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

# Direct execution sets sys.path[0] to tests/, so add the repository root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.recent_sentence_deduplicator as dedup

class RecentSentenceDeduplicatorTests(unittest.TestCase):
    def test_replaces_exact_repeated_generic_sentences_and_preserves_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = "That keeps the read falsifiable; the next measurable reaction either supports the structure or weakens it."
            second = "The available evidence supports a scenario to test, not certainty about the next candle."
            log = root / "publication_log.jsonl"
            log.write_text(json.dumps({"text": first + " " + second}) + "\n", encoding="utf-8")
            report = root / "draft.json"
            report.write_text(json.dumps({"draft": {"symbol": "EPIC", "post": first + " " + second + " What evidence should readers watch next?"}}), encoding="utf-8")
            out = root / "dedup.json"
            with patch.object(dedup, "LOG", log), patch.object(dedup, "OUT", out), patch.object(dedup, "REPORT_DIR", root), patch.dict("os.environ", {"DRAFT_PATH": str(report)}):
                rc = dedup.main()
            self.assertEqual(rc, 0)
            updated = json.loads(report.read_text(encoding="utf-8"))["draft"]["post"]
            self.assertEqual(updated.count("?"), 1)
            self.assertIn("What evidence should readers watch next?", updated)
            self.assertNotIn(first.rstrip("."), updated)
            self.assertNotIn(second.rstrip("."), updated)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["factual_sentences_rewritten"], 0)


    def test_repairs_repeated_quote_volume_sentence_preserving_observed_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repeated = "4M USDT in quote volume; the available 1H evidence does not justify inventing a cleaner range."
            log = root / "publication_log.jsonl"
            log.write_text(json.dumps({"text": repeated}) + "\n", encoding="utf-8")
            report = root / "draft.json"
            original = "$INIT is moving through a measurable market context. " + repeated + " What evidence would change your view on $INIT?"
            report.write_text(json.dumps({"draft": {"symbol": "INIT", "post": original}}), encoding="utf-8")
            out = root / "dedup.json"
            with patch.object(dedup, "LOG", log), patch.object(dedup, "OUT", out), patch.object(dedup, "REPORT_DIR", root), patch.dict("os.environ", {"DRAFT_PATH": str(report)}):
                rc = dedup.main()
            self.assertEqual(rc, 0)
            updated = json.loads(report.read_text(encoding="utf-8"))["draft"]["post"]
            self.assertNotIn(repeated.rstrip("."), updated)
            self.assertIn("4M USDT", updated)
            self.assertIn("high-low data is insufficient", updated)
            self.assertEqual(updated.count("?"), 1)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["changed"], 1)
            self.assertEqual(result["replacements"][0]["status"], "replaced")

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

    def test_over_budget_replacement_rolls_back_instead_of_blocking_valid_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repeated = "The next evidence point should determine whether this interpretation still holds up."
            log = root / "publication_log.jsonl"
            log.write_text(json.dumps({"text": repeated}) + "\n", encoding="utf-8")
            report = root / "draft.json"
            prefix = "$QI moved +20.4% in 24 hours. " + repeated + " "
            question = " What evidence should readers watch next?"
            # Keep the source draft valid (<=740 chars), but close enough to the
            # limit that the 6-character-longer replacement would exceed it.
            filler_length = 738 - len(prefix) - len(question)
            filler = ("market context remains uncertain and traders should compare the next response " * 10)[:filler_length]
            original = prefix + filler + question
            self.assertLessEqual(len(original), 740)
            self.assertGreater(len(original) - len(repeated) + len("For $QI, the next observed response can support this thesis or show why it no longer fits."), 740)
            report.write_text(json.dumps({"draft": {"symbol": "QI", "post": original}}), encoding="utf-8")
            out = root / "dedup.json"
            with patch.object(dedup, "LOG", log), patch.object(dedup, "OUT", out), patch.object(dedup, "REPORT_DIR", root), patch.dict("os.environ", {"DRAFT_PATH": str(report)}):
                rc = dedup.main()
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["draft"]["post"], original)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "UNCHANGED")
            self.assertEqual(result["changed"], 0)
            self.assertEqual(result["replacements"][0]["status"], "preserved_contract_no_safe_replacement")

if __name__ == "__main__":
    unittest.main()
