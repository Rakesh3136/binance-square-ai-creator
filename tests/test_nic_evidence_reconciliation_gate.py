import json
import tempfile
import unittest
from pathlib import Path
from src.nic_evidence_reconciliation_gate import validate

class GateTests(unittest.TestCase):
    def test_stale_empty_ledger_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); d=root/"data/intelligence"; d.mkdir(parents=True)
            (d/"nic_forecast_truth_ledger.jsonl").write_text("",encoding="utf-8")
            (d/"nic_forecast_outcome_events.jsonl").write_text("",encoding="utf-8")
            (d/"nic_forecast_laboratory_report.json").write_text(json.dumps({"appended_snapshots":72,"ready":12,"attempted_snapshots":72}),encoding="utf-8")
            common={"snapshot_ledger_sha256":"x","outcome_ledger_sha256":"y","snapshot_count":0,"terminal_outcome_count":0}
            (d/"nic_portfolio_reality.json").write_text(json.dumps({"source_evidence":common,"source_file_evidence":common,"status":"NOT_PROVEN","trade_or_publication_authorization":False}),encoding="utf-8")
            (d/"nic_forecast_profitability.json").write_text(json.dumps({"source_evidence":common,"resolved_forecast_count":0,"sample_count":0,"status":"NOT_PROVEN","publication_or_trade_authorization":False}),encoding="utf-8")
            with self.assertRaisesRegex(AssertionError,"reports appended snapshots"):
                validate(root)

if __name__=="__main__": unittest.main()
