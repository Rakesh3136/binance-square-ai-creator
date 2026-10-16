import unittest

from src.nic_forecast_evidence_reconcile import merge_rows, parse_jsonl, render_jsonl


class ForecastEvidenceReconcileTests(unittest.TestCase):
    def test_merge_deduplicates_by_immutable_id_and_keeps_current_order(self):
        current = [{"forecast_id": "a", "value": 1}, {"forecast_id": "b", "value": 2}]
        incoming = [{"forecast_id": "b", "value": 999}, {"forecast_id": "c", "value": 3}]
        merged = merge_rows(current, incoming, lambda row: row["forecast_id"])
        self.assertEqual(merged, [
            {"forecast_id": "a", "value": 1},
            {"forecast_id": "b", "value": 2},
            {"forecast_id": "c", "value": 3},
        ])

    def test_jsonl_round_trip_and_blank_lines(self):
        rows = parse_jsonl('{"id":"one"}\n\n{"id":"two"}\n')
        self.assertEqual(parse_jsonl(render_jsonl(rows)), rows)

    def test_invalid_jsonl_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_jsonl('{"id":\n', "broken.jsonl")


if __name__ == "__main__":
    unittest.main()
