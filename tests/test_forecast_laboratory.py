import unittest

from src.forecast_laboratory import analyze


class ForecastLaboratoryTests(unittest.TestCase):
    def test_compares_bull_and_bear_hypotheses_without_claiming_probability(self):
        payload = {"observations": [
            {"asset": "ABCUSDT", "timestamp": "2026-10-01T00:00:00Z", "return_pct": 0.2, "volume_change_pct": 5, "trend_score": 0.3, "volatility_pct": 1.0},
            {"asset": "ABCUSDT", "timestamp": "2026-10-02T00:00:00Z", "return_pct": 1.0, "volume_change_pct": 10, "trend_score": 0.8, "volatility_pct": 1.2},
        ], "outcomes": []}
        report = analyze(payload)
        self.assertEqual(report["status"], "RESEARCH_ONLY")
        self.assertEqual(report["forecast_count"], 1)
        forecast = report["forecasts"][0]
        self.assertAlmostEqual(forecast["bull_hypothesis_score"] + forecast["bear_hypothesis_score"], 1.0)
        self.assertIn("not a calibrated probability", forecast["interpretation"])
        self.assertEqual(forecast["regime"]["label"], "INSUFFICIENT_HISTORY")

    def test_flags_extended_move_without_authorizing_entry(self):
        report = analyze({"observations": [
            {"asset": "XYZ", "timestamp": "2026-10-01T00:00:00Z", "return_pct": 8.0, "volume_change_pct": 40, "trend_score": 0.9, "volatility_pct": 4.0}
        ]})
        self.assertTrue(report["forecasts"][0]["large_move_caution"])
        self.assertTrue(any("avoid treating" in warning for warning in report["forecasts"][0]["warnings"]))

    def test_calculates_brier_score_for_resolved_outcomes(self):
        report = analyze({"observations": [], "outcomes": [
            {"asset": "ABC", "timestamp": "2026-10-01T00:00:00Z", "bull_probability": 0.8, "horizon_return_pct": 2.0},
            {"asset": "ABC", "timestamp": "2026-10-02T00:00:00Z", "bull_probability": 0.3, "horizon_return_pct": -1.0},
        ]})
        self.assertEqual(report["historical_calibration"]["sample_count"], 2)
        self.assertAlmostEqual(report["historical_calibration"]["bull_brier_score"], 0.065)

    def test_rejects_timezone_naive_timestamps(self):
        with self.assertRaises(ValueError):
            analyze({"observations": [{"asset": "ABC", "timestamp": "2026-10-01T00:00:00", "return_pct": 0}]})

    def test_rejects_invalid_probability(self):
        with self.assertRaises(ValueError):
            analyze({"outcomes": [{"asset": "ABC", "timestamp": "2026-10-01T00:00:00Z", "bull_probability": 1.2, "horizon_return_pct": 1}]})


if __name__ == "__main__":
    unittest.main()
