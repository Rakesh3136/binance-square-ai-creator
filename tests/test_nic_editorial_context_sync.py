import importlib.util
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nic_editorial_context_sync", ROOT / "src" / "nic_editorial_context_sync.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
evaluate = module.evaluate

class EditorialContextSyncTests(unittest.TestCase):
    def fixtures(self):
        now = datetime.now(timezone.utc)
        stamp = now.isoformat()
        routing = {"publish": True, "decision": "EDITORIAL_SIGNAL", "decision_id": "d1", "generated_at": stamp, "selected": {"symbol": "MAGIC"}}
        frozen = {"symbol": "MAGIC", "frozen_at": stamp, "category": "technical_setup", "instruction": "Explain the evidence and invalidation."}
        eligibility = {"eligible": True, "publication_mode": "EDITORIAL", "trade_authorized": False, "generated_at": stamp}
        preflight = {"selected_opportunity": {"symbol": "QNT", "category": "stale"}, "creator_brain_decision": {"symbol": "QNT"}}
        return now, routing, frozen, eligibility, preflight

    def test_syncs_current_frozen_symbol_and_removes_stale_brain(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertTrue(result["publish"])
        self.assertEqual(result["preflight"]["selected_opportunity"]["symbol"], "MAGIC")
        self.assertNotIn("creator_brain_decision", result["preflight"])
        self.assertFalse(result["trade_authorized"])

    def test_asset_mismatch_blocks(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        frozen["symbol"] = "QNT"
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertFalse(result["publish"])

    def test_trade_mode_blocks_editorial_sync(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        eligibility["publication_mode"] = "TRADE"
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertFalse(result["publish"])

    def test_stale_routing_blocks(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        routing["generated_at"] = (now - timedelta(hours=2)).isoformat()
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertFalse(result["publish"])

    def test_no_trade_authorization_is_required(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        eligibility["trade_authorized"] = True
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertFalse(result["publish"])

if __name__ == "__main__":
    unittest.main()
