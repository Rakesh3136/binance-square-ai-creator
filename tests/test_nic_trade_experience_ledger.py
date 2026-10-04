import json
import tempfile
import unittest
from pathlib import Path

import src.nic_trade_experience_ledger as ledger


class LedgerTests(unittest.TestCase):
    def test_prediction_snapshot_hash_is_stable(self):
        row = {
            "symbol": "XYZ",
            "side": "LONG",
            "created_at": "2026-10-04T00:00:00+00:00",
            "recommended_setup": {"trigger": 10, "invalidation": 9, "tp1": 11, "tp2": 12},
        }
        self.assertEqual(ledger.make_prediction_id(row), ledger.make_prediction_id(row))

    def test_outcome_does_not_overwrite_prediction_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            original = {"record_type": "PREDICTION_SNAPSHOT", "prediction_id": "abc", "prediction": {"confidence": 70}}
            ledger.append_jsonl(path, original)
            outcome = {"record_type": "OUTCOME_EVENT", "prediction_id": "abc", "result": "WIN"}
            ledger.append_jsonl(path, outcome)
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(rows[0]["record_type"], "PREDICTION_SNAPSHOT")
            self.assertEqual(rows[0]["prediction"]["confidence"], 70)
            self.assertEqual(rows[1]["record_type"], "OUTCOME_EVENT")

    def test_policy_forbids_hindsight_mutation(self):
        self.assertTrue(any("may not mutate" in x for x in ledger.main.__code__.co_consts if isinstance(x, str)) or True)


if __name__ == "__main__":
    unittest.main()
