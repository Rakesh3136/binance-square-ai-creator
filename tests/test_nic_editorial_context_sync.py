import importlib.util
import unittest
import contextlib
import io
import json
import tempfile
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


    def test_exhausted_timing_downgrades_stale_setup_to_research(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        frozen.update({
            "category": "technical_setup", "lane": "technical_setup",
            "trade_setup": {"entry": 10, "sl": 9, "tp1": 12},
            "entry_trigger": 10, "tp1": 12, "sl": 9, "direction": "LONG",
        })
        eligibility["selected"] = {
            "symbol": "MAGIC", "category": "research_insight",
            "timing_state": "EXHAUSTED",
            "timing_reason": "move is too extended for a fresh entry",
        }
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertTrue(result["publish"])
        selected = result["preflight"]["selected_opportunity"]
        self.assertEqual(selected["category"], "research_insight")
        self.assertEqual(selected["lane"], "research_insight")
        self.assertNotIn("trade_setup", selected)
        self.assertNotIn("entry_trigger", selected)
        self.assertNotIn("tp1", selected)
        self.assertNotIn("sl", selected)
        self.assertIn("timing is exhausted", selected["instruction"])

    def test_eligibility_asset_mismatch_blocks_sync(self):
        now, routing, frozen, eligibility, preflight = self.fixtures()
        eligibility["selected"] = {"symbol": "QNT", "category": "research_insight"}
        result = evaluate(routing, frozen, eligibility, preflight, now)
        self.assertFalse(result["publish"])
        self.assertIn("publication eligibility asset does not match frozen opportunity", result["reasons"])

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

    def test_technical_enricher_respects_synced_research_only_lane(self):
        tech_spec = importlib.util.spec_from_file_location("technical_enricher", ROOT / "src" / "technical_enricher.py")
        tech = importlib.util.module_from_spec(tech_spec)
        tech_spec.loader.exec_module(tech)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight_path = root / "editorial_preflight.json"
            frozen_path = root / "authoritative_opportunity.json"
            preflight_path.write_text(json.dumps({"selected_opportunity": {
                "symbol": "GNS", "category": "research_insight", "lane": "research_insight",
                "timing_state": "EXHAUSTED",
                "instruction": "Explain the move; do not provide trade levels."
            }}), encoding="utf-8")
            frozen_path.write_text(json.dumps({"symbol": "GNS", "category": "technical_setup",
                "lane": "technical_setup", "trade_setup": {"entry": 0.5, "sl": 0.4, "tp1": 0.6}}), encoding="utf-8")
            tech.PREFLIGHT = preflight_path
            tech.AUTHORITATIVE = frozen_path
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                tech.main()
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "SKIP")
            self.assertEqual(result["category"], "research_insight")
            self.assertEqual(result["timing_state"], "EXHAUSTED")
            self.assertIn("trade levels suppressed", result["reason"])


if __name__ == "__main__":
    unittest.main()
