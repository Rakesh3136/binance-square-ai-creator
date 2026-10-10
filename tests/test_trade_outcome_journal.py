import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.trade_outcome_journal import append_record, read_latest, summary, validate_record


def example(**overrides):
    record = {
        "trade_id": "example-eth-2026-10-08",
        "symbol": "ethusdt",
        "direction": "short",
        "published_at": "2026-10-08T12:00:00Z",
        "entry_price": 2581,
        "stop_loss": 2596.5,
        "outcome": "unresolved",
        "outcome_evidence": [],
        "prediction_quality": "not_assessed",
        "quality_evidence": [],
        "learning_status": "pending",
    }
    record.update(overrides)
    return record


class TradeOutcomeJournalTests(unittest.TestCase):
    def test_unverified_claim_stays_unresolved(self):
        normalized = validate_record(example())
        self.assertEqual(normalized["outcome"], "unresolved")
        self.assertIsNone(normalized["realized_pnl"])

    def test_resolved_outcome_requires_evidence(self):
        with self.assertRaisesRegex(ValueError, "requires outcome_evidence"):
            validate_record(example(outcome="verified_win"))

    def test_learning_cannot_be_claimed_before_assessment(self):
        with self.assertRaisesRegex(ValueError, "cannot be marked incorporated"):
            validate_record(example(learning_status="incorporated"))

    def test_append_and_latest_event_are_traceable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.jsonl"
            append_record(example(), path)
            append_record(example(outcome="verified_win",
                                  outcome_evidence=["exchange-close-record:example"],
                                  prediction_quality="supported",
                                  quality_evidence=["timestamped-market-snapshot"],
                                  learning_status="incorporated"), path)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
            latest = read_latest(path)["example-eth-2026-10-08"]
            self.assertEqual(latest["outcome"], "verified_win")
            self.assertEqual(summary(path)["verified_outcome_count"], 1)

    def test_invalid_direction_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "direction"):
            validate_record(example(direction="maybe"))


if __name__ == "__main__":
    unittest.main()
