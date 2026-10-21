import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.run_creator_intelligence import benchmark_refresh_due


class BenchmarkAutoRefreshTests(unittest.TestCase):
    def test_missing_state_triggers_first_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(benchmark_refresh_due(datetime(2026, 10, 17, tzinfo=timezone.utc), Path(tmp) / "missing.json"))

    def test_successful_collection_refreshes_after_24_hours(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"last_run": "2026-10-16T00:00:00+00:00", "last_status": "PUBLIC_BENCHMARKS_AVAILABLE"}), encoding="utf-8")
            self.assertFalse(benchmark_refresh_due(datetime(2026, 10, 16, 12, tzinfo=timezone.utc), path))
            self.assertTrue(benchmark_refresh_due(datetime(2026, 10, 17, 0, 1, tzinfo=timezone.utc), path))

    def test_unavailable_feed_retries_after_one_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"last_run": "2026-10-16T00:00:00+00:00", "last_status": "PUBLIC_FEED_UNAVAILABLE_OR_EMPTY"}), encoding="utf-8")
            self.assertFalse(benchmark_refresh_due(datetime(2026, 10, 16, 12, tzinfo=timezone.utc), path))
            self.assertTrue(benchmark_refresh_due(datetime(2026, 10, 17, 0, 1, tzinfo=timezone.utc), path))

    def test_naive_timestamp_fails_closed_to_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({"last_run": "2026-10-16T00:00:00", "last_status": "PUBLIC_BENCHMARKS_AVAILABLE"}), encoding="utf-8")
            self.assertTrue(benchmark_refresh_due(datetime(2026, 10, 16, 12, tzinfo=timezone.utc), path))


if __name__ == "__main__":
    unittest.main()
