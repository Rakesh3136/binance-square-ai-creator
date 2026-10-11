import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Executing this file directly puts tests/ (not the repository root) on sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.nic_evidence_reconciliation_gate import validate


class GateTests(unittest.TestCase):
    def test_stale_empty_ledger_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "data/intelligence"
            d.mkdir(parents=True)
            (d / "nic_forecast_truth_ledger.jsonl").write_text("", encoding="utf-8")
            (d / "nic_forecast_outcome_events.jsonl").write_text("", encoding="utf-8")
            (d / "nic_forecast_laboratory_report.json").write_text(
                json.dumps({"appended_snapshots": 72, "ready": 12, "attempted_snapshots": 72}),
                encoding="utf-8",
            )
            common = {
                "snapshot_ledger_sha256": "x",
                "outcome_ledger_sha256": "y",
                "snapshot_count": 0,
                "terminal_outcome_count": 0,
            }
            (d / "nic_portfolio_reality.json").write_text(
                json.dumps({
                    "source_evidence": common,
                    "source_file_evidence": common,
                    "status": "NOT_PROVEN",
                    "trade_or_publication_authorization": False,
                }),
                encoding="utf-8",
            )
            (d / "nic_forecast_profitability.json").write_text(
                json.dumps({
                    "source_evidence": common,
                    "resolved_forecast_count": 0,
                    "sample_count": 0,
                    "status": "NOT_PROVEN",
                    "publication_or_trade_authorization": False,
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                AssertionError, "reports appended snapshots"
            ):
                validate(root)


    def test_reported_appended_id_must_exist_in_persisted_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "data/intelligence"
            d.mkdir(parents=True)
            snapshot_path = d / "nic_forecast_truth_ledger.jsonl"
            outcome_path = d / "nic_forecast_outcome_events.jsonl"
            snapshot_path.write_text(json.dumps({"forecast_id": "persisted-id"}) + "\n", encoding="utf-8")
            outcome_path.write_text("", encoding="utf-8")
            sh = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            eh = hashlib.sha256(outcome_path.read_bytes()).hexdigest()
            common = {
                "snapshot_ledger_sha256": sh,
                "outcome_ledger_sha256": eh,
                "snapshot_count": 1,
                "terminal_outcome_count": 0,
            }
            (d / "nic_forecast_laboratory_report.json").write_text(
                json.dumps({
                    "appended_snapshots": 1,
                    "persisted_snapshot_count": 1,
                    "appended_forecast_ids": ["not-in-ledger"],
                }), encoding="utf-8"
            )
            (d / "nic_portfolio_reality.json").write_text(
                json.dumps({
                    "source_evidence": common, "source_file_evidence": common,
                    "status": "NOT_PROVEN", "trade_or_publication_authorization": False,
                }), encoding="utf-8"
            )
            (d / "nic_forecast_profitability.json").write_text(
                json.dumps({
                    "source_evidence": common, "resolved_forecast_count": 0, "sample_count": 0,
                    "status": "NOT_PROVEN", "publication_or_trade_authorization": False,
                }), encoding="utf-8"
            )
            with self.assertRaisesRegex(AssertionError, "appended forecast IDs absent"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
