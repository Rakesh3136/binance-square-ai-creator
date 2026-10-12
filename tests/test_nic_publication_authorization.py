import importlib.util, unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load_module(name, rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

auth=load_module("nic_publication_authorization","src/nic_publication_authorization.py")
audit=load_module("nic_publication_proof_audit","src/nic_publication_proof_audit.py")
NOW=datetime.now(timezone.utc).isoformat()

class EditorialAuthorizationTests(unittest.TestCase):
    def fixtures(self):
        return (
            {"editorial_auto_publication_enabled":True,"editorial_mode":"EDITORIAL_ONLY","trade_signal_publication_enabled":False,"live_orders_enabled":False,"requires_human_review_for_editorial":False},
            {"eligible":True,"publication_mode":"EDITORIAL","trade_authorized":False,"generated_at":NOW},
            {"publish":True,"decision":"EDITORIAL_SIGNAL","generated_at":NOW},
            {"publish":True,"status":"EDITORIAL_ELIGIBLE","trade_authorized":False,"generated_at":NOW},
            "Research note: $MAGIC has a conditional market structure worth watching; no entry, stop, target, or instruction is provided."
        )
    def test_explicit_standing_policy_authorizes_only_editorial(self):
        result=auth.evaluate(*self.fixtures())
        self.assertTrue(result["authorized"]); self.assertFalse(result["trade_signal_publication_authorized"]); self.assertFalse(result["live_orders_authorized"]); self.assertFalse(result["human_review_claimed"])
    def test_trade_mode_never_authorized(self):
        p,e,r,l,t=self.fixtures(); e["publication_mode"]="TRADE"
        self.assertFalse(auth.evaluate(p,e,r,l,t)["authorized"])
    def test_missing_explicit_trade_denial_blocks(self):
        p,e,r,l,t=self.fixtures(); e["trade_authorized"]=True
        self.assertFalse(auth.evaluate(p,e,r,l,t)["authorized"])
    def test_stale_routing_blocks(self):
        p,e,r,l,t=self.fixtures(); r["generated_at"]="2020-01-01T00:00:00+00:00"
        self.assertFalse(auth.evaluate(p,e,r,l,t)["authorized"])
    def test_actionable_trade_levels_block(self):
        p,e,r,l,t=self.fixtures(); t="Entry: 1.2, Stop-loss: 1.0"
        self.assertFalse(auth.evaluate(p,e,r,l,t)["authorized"])
    def test_disabled_policy_blocks(self):
        p,e,r,l,t=self.fixtures(); p["editorial_auto_publication_enabled"]=False
        self.assertFalse(auth.evaluate(p,e,r,l,t)["authorized"])

class PublicationProofAuditTests(unittest.TestCase):
    def test_current_run_post_id_and_link_confirm_publication(self):
        result=audit.evaluate({"github_run_id":"123","status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","post_id":"abc123","link":"https://www.binance.com/square/post/abc123"},"123","success")
        self.assertEqual(result["status"],"CONFIRMED_PUBLISHED"); self.assertTrue(result["verified"])
    def test_old_run_result_is_not_proof(self):
        result=audit.evaluate({"github_run_id":"old","status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","post_id":"abc123","link":"https://www.binance.com/square/post/abc123"},"123","skipped")
        self.assertEqual(result["status"],"NO_VERIFIED_PUBLICATION"); self.assertFalse(result["verified"]); self.assertIsNone(result["post_id"])
    def test_504_is_unconfirmed(self):
        result=audit.evaluate({"github_run_id":"123","status":"PUBLISHED_SUBMITTED_504"},"123","success")
        self.assertEqual(result["status"],"SUBMISSION_UNCONFIRMED"); self.assertFalse(result["verified"])
    def test_success_without_id_is_not_proof(self):
        result=audit.evaluate({"github_run_id":"123","status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","link":"https://www.binance.com/square/post/abc"},"123","success")
        self.assertEqual(result["status"],"NO_VERIFIED_PUBLICATION"); self.assertFalse(result["verified"])

if __name__=="__main__": unittest.main()
