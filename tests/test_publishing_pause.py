"""Regression test: automatic publishing must remain paused by default."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("binance_square_publisher", ROOT / "src" / "binance_square_publisher.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PublishingPauseTest(unittest.TestCase):
    def test_default_mode_blocks_publication_before_credentials_or_network(self):
        old_enabled = os.environ.pop("PUBLISHING_ENABLED", None)
        old_openapi = os.environ.pop("BINANCE_SQUARE_OPENAPI_KEY", None)
        old_api = os.environ.pop("BINANCE_SQUARE_API_KEY", None)
        old_result = publisher.RESULT_PATH
        try:
            with tempfile.TemporaryDirectory() as directory:
                publisher.RESULT_PATH = Path(directory) / "publication_result.json"
                result = publisher.main()
                payload = json.loads(publisher.RESULT_PATH.read_text(encoding="utf-8"))
                self.assertEqual(result, 0)
                self.assertEqual(payload["status"], "PUBLISHING_PAUSED")
                self.assertEqual(payload["current_run_publication"], "NO_NEW_PUBLICATION")
                self.assertIsNone(payload["post_id"])
        finally:
            publisher.RESULT_PATH = old_result
            if old_enabled is not None:
                os.environ["PUBLISHING_ENABLED"] = old_enabled
            if old_openapi is not None:
                os.environ["BINANCE_SQUARE_OPENAPI_KEY"] = old_openapi
            if old_api is not None:
                os.environ["BINANCE_SQUARE_API_KEY"] = old_api



    def test_editorial_only_mode_allows_non_actionable_editorial(self):
        ok, _ = publisher.editorial_only_publication_check(
            "A research note comparing liquidity and volatility without a trade setup.",
            {"publication_mode": "EDITORIAL", "trade_authorized": False},
            "EDITORIAL_ONLY",
        )
        self.assertTrue(ok)

    def test_trade_mode_never_passes_editorial_publication_guard(self):
        ok, _ = publisher.editorial_only_publication_check(
            "Market setup", {"publication_mode": "TRADE", "trade_authorized": True},
            "EDITORIAL_ONLY",
        )
        self.assertFalse(ok)

    def test_actionable_trade_levels_block_editorial_auto_publication(self):
        for text in ("Entry: 100.5", "Stop-loss: 98", "TP1: 105", "Buy now"):
            ok, _ = publisher.editorial_only_publication_check(
                text, {"publication_mode": "EDITORIAL", "trade_authorized": False},
                "EDITORIAL_ONLY",
            )
            self.assertFalse(ok)

    def test_missing_or_wrong_mode_fails_closed(self):
        ok, _ = publisher.editorial_only_publication_check(
            "Research note", {}, "ALL_CONTENT"
        )
        self.assertFalse(ok)

    def test_workflow_reactivates_only_after_final_quality_authorization(self):
        workflow = (ROOT / ".github" / "workflows" / "autonomous-market-creator.yml").read_text(encoding="utf-8")

        def step_block(name):
            marker = f"      - name: {name}"
            start = workflow.index(marker)
            end = workflow.find("\n      - name:", start + len(marker))
            return workflow[start:] if end < 0 else workflow[start:end]

        authorization = step_block("NIC editorial automatic-publication authorization")
        payload = step_block("Build final publication payload")
        publisher_step = step_block("Extract publication and submit to Binance Square")
        final_gate = step_block("Final NIC 21 and editorial revalidation")

        self.assertIn("steps.final_quality_gate.outputs.publish == 'true'", authorization)
        self.assertIn("if: ${{ false }}", payload)
        self.assertIn("if: ${{ false }}", publisher_step)
        self.assertIn("PUBLISHING_ENABLED: 'false'", publisher_step)
        self.assertIn("Emergency pause", payload)
        self.assertIn("Independent hard stop", publisher_step)
        self.assertIn("DRAFT_PATH:", final_gate)

    def test_publisher_requires_exact_text_hashes_from_all_quality_gates(self):
        text = "Verified editorial research without trade instructions."
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        authorization = {"authorized": True, "publication_mode": "EDITORIAL_ONLY",
                         "trade_signal_publication_authorized": False, "live_orders_authorized": False,
                         "draft_sha256": digest}
        nic21 = {"status": "PASS", "draft_sha256": digest}
        lane = {"publish": True, "status": "EDITORIAL_ELIGIBLE",
                "trade_authorized": False, "draft_sha256": digest}
        self.assertTrue(publisher.verify_quality_authorization(text, authorization, nic21, lane)[0])
        nic21["status"] = "BLOCKED"
        self.assertFalse(publisher.verify_quality_authorization(text, authorization, nic21, lane)[0])

if __name__ == "__main__":
    unittest.main()
