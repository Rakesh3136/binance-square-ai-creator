import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_opportunity_desk import rotation_candidates, long_term_watchlist, build


def asset(symbol, move, flow=60, rs=None, volume=1.4, oi=2.0, funding=0.0001):
    return {
        "symbol": symbol,
        "market_context": {"spot_move_pct": move},
        "relative_strength_to_btc": rs,
        "multitimeframe": {"flow_proxy_score": flow, "confidence": 70},
        "timeframes": {"1h": {"volume_ratio": volume, "taker_buy_ratio_20": 0.57}},
        "futures": {"open_interest_change_6h_pct": oi, "funding_rate": funding},
        "trade_setup": {"side": "WAIT"},
    }


class RotationDeskTests(unittest.TestCase):
    def test_btc_drop_and_relative_strength_flags_early_watch_not_whale_fact(self):
        doc = {"assets": [asset("BTC", -3.0), asset("SOL", 1.0, rs=4.0)]}
        result = rotation_candidates(doc)
        self.assertEqual(result["status"], "ROTATION_CANDIDATES_FOUND")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["symbol"], "SOL")
        self.assertEqual(candidate["state"], "EARLY_ROTATION_WATCH")
        self.assertFalse(candidate["wallet_level_flow_verified"])
        self.assertTrue(any("not proof" in result["interpretation"].lower() for _ in [0]))

    def test_missing_btc_fails_closed(self):
        result = rotation_candidates({"assets": [asset("SOL", 3.0)]})
        self.assertEqual(result["status"], "INSUFFICIENT_BTC_REFERENCE")
        self.assertEqual(result["candidates"], [])

    def test_late_move_is_not_chased(self):
        result = rotation_candidates({"assets": [asset("BTC", -2.0), asset("SOL", 11.0, rs=13.0)]})
        self.assertEqual(result["candidates"][0]["state"], "LATE_MOVE_DO_NOT_CHASE")

    def test_crowded_long_overrides_early_watch(self):
        result = rotation_candidates({"assets": [asset("BTC", -2.0), asset("SOL", 1.0, rs=4.0, funding=0.002)]})
        self.assertEqual(result["candidates"][0]["state"], "CROWDING_RISK")

    def test_long_term_projects_need_multiple_categories_and_domains(self):
        rows = [
            {"symbol": "ABC", "evidence_type": "adoption", "source_url": "https://docs.example.org/adoption", "claim": "Active users rose", "published_at": "2026-10-01"},
            {"symbol": "ABC", "evidence_type": "developer_activity", "source_url": "https://github.example.net/dev", "claim": "Developer contributions rose"},
            {"symbol": "ABC", "evidence_type": "security", "source_url": "https://audit.example.com/report", "claim": "Independent audit published"},
        ]
        result = long_term_watchlist(rows)
        self.assertEqual(result[0]["status"], "LONG_TERM_RESEARCH_WATCH")
        self.assertEqual(result[0]["independent_source_domains"], 3)
        self.assertTrue(result[0]["not_a_price_prediction"])

    def test_long_term_project_with_single_category_is_not_promoted(self):
        rows = [{"symbol": "ABC", "evidence_type": "adoption", "source_url": "https://example.org/users", "claim": "Users rose"}]
        result = long_term_watchlist(rows)
        self.assertEqual(result[0]["status"], "INSUFFICIENT_FUNDAMENTAL_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
