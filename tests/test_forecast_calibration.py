import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.forecast_calibration import calibration_report, validate_forecast


def forecast(fid, p, result="unresolved", evidence=None, **extra):
    item = {
        "forecast_id": fid,
        "symbol": "ETHUSDT",
        "probability_up": p,
        "resolved_direction": result,
        "resolution_evidence": evidence or [],
        "horizon": "24h",
        "strategy": "test",
    }
    item.update(extra)
    return item


class ForecastCalibrationTests(unittest.TestCase):
    def test_unresolved_forecasts_are_not_scored(self):
        report = calibration_report([forecast("f1", 0.8)])
        self.assertIsNone(report["brier_score"])
        self.assertEqual(report["unresolved_count"], 1)

    def test_brier_score_uses_only_evidence_backed_resolved_forecasts(self):
        report = calibration_report([
            forecast("f1", 0.8, "up", ["snapshot:1"]),
            forecast("f2", 0.8, "down", ["snapshot:2"]),
            forecast("f3", 0.1),
        ])
        self.assertAlmostEqual(report["brier_score"], ((0.8-1)**2 + (0.8-0)**2) / 2)
        self.assertEqual(report["resolved_count"], 2)
        self.assertEqual(report["unresolved_count"], 1)

    def test_resolved_without_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "require resolution_evidence"):
            validate_forecast(forecast("f1", 0.7, "up"))

    def test_probability_bounds_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            validate_forecast(forecast("f1", 1.2))

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate forecast_id"):
            calibration_report([
                forecast("same", 0.7, "up", ["snapshot:1"]),
                forecast("same", 0.3, "down", ["snapshot:2"]),
            ])

    def test_perfect_and_wrong_forecasts_score_correctly(self):
        perfect = calibration_report([forecast("p", 1.0, "up", ["e"])])
        wrong = calibration_report([forecast("w", 1.0, "down", ["e"])])
        self.assertEqual(perfect["brier_score"], 0.0)
        self.assertEqual(wrong["brier_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
