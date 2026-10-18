import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_market_flow_founder_intelligence import build


class FlowFounderTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, 5, 0, tzinfo=timezone.utc)
        stamp = (self.now - timedelta(minutes=10)).isoformat()
        self.market = {"generated_at": stamp, "top_content_signals": [{"symbol": "BTCUSDT", "price_change_percent": -2.5}]}
        self.flow = {"generated_at": stamp, "top_flow_candidates": [
            {"symbol": "AAAUSDT", "last_price": 1, "price_change_percent": 2, "relative_strength_24h": 4,
             "oi_change_3h_pct": 5, "quote_volume_usdt": 1000000, "flow_state": "WATCH", "evidence": ["relative_strength_24h"]},
            {"symbol": "PUMPUSDT", "price_change_percent": 9, "relative_strength_24h": 8,
             "oi_change_3h_pct": 10, "quote_volume_usdt": 10000000, "flow_state": "LATE"}]}
        self.capital = {"generated_at": stamp, "market_rotation": {"market_regime": "RISK_OFF"}}
        self.predictions = {"generated_at": stamp, "candidates": []}

    def test_fresh_btc_weakness_is_only_a_screen(self):
        report = build(self.market, self.flow, self.capital, self.now)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["flow_conclusion"], "BTC_WEAKNESS_ROTATION_SCREEN")
        self.assertEqual([x["symbol"] for x in report["early_screen_candidates"]], ["AAA"])
        self.assertIn("do not prove", report["capital_flow_interpretation"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["trade_authorized"])

    def test_stale_input_blocks_ranking(self):
        self.market["generated_at"] = (self.now - timedelta(hours=3)).isoformat()
        report = build(self.market, self.flow, self.capital, self.now)
        self.assertEqual(report["status"], "MARKET_ANALYSIS_BLOCKED_STALE_INPUTS")
        self.assertEqual(report["early_screen_candidates"], [])

    def test_missing_timestamp_fails_closed(self):
        self.flow.pop("generated_at")
        report = build(self.market, self.flow, self.capital, self.now)
        self.assertFalse(report["freshness"]["full_universe_flow"]["fresh"])
        self.assertEqual(report["early_screen_candidates"], [])

    def test_long_term_projects_require_fundamentals(self):
        report = build(self.market, self.flow, self.capital, self.now)
        self.assertEqual(report["long_term_project_research"]["status"], "FUNDAMENTAL_EVIDENCE_REQUIRED")

    def test_founder_ideas_are_hypotheses(self):
        report = build(self.market, self.flow, self.capital, self.now)
        founder = report["founder_opportunity_brief"]
        self.assertEqual(founder["status"], "HYPOTHESES_TO_VALIDATE_NOT_MARKET_FACTS")
        self.assertGreaterEqual(len(founder["opportunity_hypotheses"]), 3)


if __name__ == "__main__":
    unittest.main()
