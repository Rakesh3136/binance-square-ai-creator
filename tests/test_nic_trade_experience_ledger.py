import json
import tempfile
import unittest
import sys
from pathlib import Path

# GitHub Actions invokes this file as `python tests/...`; make repository-root
# imports deterministic instead of relying on the current Python path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.nic_trade_experience_ledger as ledger

class LedgerTests(unittest.TestCase):
    def test_prediction_id_is_stable(self):
        row={"symbol":"XYZ","side":"LONG","created_at":"2026-10-04T00:00:00+00:00",
             "recommended_setup":{"trigger":10,"invalidation":9,"tp1":11,"tp2":12}}
        self.assertEqual(ledger.make_prediction_id(row),ledger.make_prediction_id(row))

    def test_snapshot_and_outcome_are_separate_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            ledger.append(path,{"record_type":"PREDICTION_SNAPSHOT","prediction_id":"abc","prediction":{"confidence":70}})
            ledger.append(path,{"record_type":"OUTCOME_EVENT","prediction_id":"abc","event_id":"e1","outcome":"WIN"})
            rows=[json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(rows[0]["prediction"]["confidence"],70)
            self.assertEqual(rows[1]["record_type"],"OUTCOME_EVENT")
            self.assertEqual(rows[1]["prediction_id"],"abc")

    def test_duplicate_event_id_is_a_distinct_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"ledger.jsonl"
            ledger.append(path,{"record_type":"OUTCOME_EVENT","prediction_id":"abc","event_id":"e1","outcome":"WIN"})
            ids={json.loads(x)["event_id"] for x in path.read_text().splitlines()}
            self.assertEqual(ids,{"e1"})

    def test_terminal_policy_excludes_non_terminal(self):
        self.assertNotIn("AMBIGUOUS",ledger.TERMINAL)

if __name__=="__main__":
    unittest.main()
