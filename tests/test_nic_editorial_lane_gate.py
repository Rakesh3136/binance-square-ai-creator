import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nic_editorial_lane_gate", ROOT / "src" / "nic_editorial_lane_gate.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
evaluate = module.evaluate
NOW = datetime.now(timezone.utc).isoformat()


class EditorialLaneGateTest(unittest.TestCase):
    def fixtures(self):
        return (
            {"eligible": True, "publication_mode": "EDITORIAL", "trade_authorized": False, "generated_at": NOW},
            {"publish": True, "generated_at": NOW},
            {"decision": "EDITORIAL", "generated_at": NOW},
        )

    def test_current_editorial_cycle_passes_without_trade_authorization(self):
        e, r, c = self.fixtures()
        result = evaluate(e, r, c)
        self.assertTrue(result["publish"])
        self.assertFalse(result["trade_authorized"])

    def test_trade_mode_never_passes_editorial_lane(self):
        e, r, c = self.fixtures()
        e["publication_mode"] = "TRADE"
        self.assertFalse(evaluate(e, r, c)["publish"])

    def test_missing_trade_denial_fails_closed(self):
        e, r, c = self.fixtures()
        e["trade_authorized"] = True
        self.assertFalse(evaluate(e, r, c)["publish"])

    def test_stale_routing_fails_closed(self):
        e, r, c = self.fixtures()
        r["generated_at"] = "2020-01-01T00:00:00+00:00"
        self.assertFalse(evaluate(e, r, c)["publish"])

    def test_non_editorial_decision_fails_closed(self):
        e, r, c = self.fixtures()
        c["decision"] = "TRADE"
        self.assertFalse(evaluate(e, r, c)["publish"])

    def test_actionable_levels_are_blocked(self):
        e, r, c = self.fixtures()
        draft = {"draft": {"post": "OSMO entry: 0.0525, stop-loss: 0.036, target: 0.066."}}
        market = {"generated_at": NOW, "top_gainers": [{"symbol": "OSMOUSDT", "price_change_percent": 2.0}]}
        result = evaluate(e, r, c, draft=draft, market=market, symbol="OSMO")
        self.assertFalse(result["publish"])
        self.assertTrue(any("actionable trade" in reason for reason in result["reasons"]))

    def test_extended_setup_like_editorial_is_blocked(self):
        e, r, c = self.fixtures()
        draft = {"draft": {"post": "OSMO is at a breakout; watch resistance and support."}}
        market = {"generated_at": NOW, "top_gainers": [{"symbol": "OSMOUSDT", "price_change_percent": 18.0}]}
        result = evaluate(e, r, c, draft=draft, market=market, symbol="OSMO")
        self.assertFalse(result["publish"])
        self.assertTrue(any("already extended" in reason for reason in result["reasons"]))

    def test_setup_like_post_missing_market_evidence_is_blocked(self):
        e, r, c = self.fixtures()
        draft = {"draft": {"post": "OSMO breakout with support and resistance levels."}}
        result = evaluate(e, r, c, draft=draft, market={}, symbol="OSMO")
        self.assertFalse(result["publish"])

    def test_non_setup_editorial_does_not_need_price_extension_data(self):
        e, r, c = self.fixtures()
        draft = {"draft": {"post": "What the latest governance proposal means for Cosmos users."}}
        result = evaluate(e, r, c, draft=draft, market={}, symbol="OSMO")
        self.assertTrue(result["publish"])


if __name__ == "__main__":
    unittest.main()
