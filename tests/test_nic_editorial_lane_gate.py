import importlib.util
import unittest
from pathlib import Path
from datetime import datetime, timezone

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

if __name__ == "__main__":
    unittest.main()
