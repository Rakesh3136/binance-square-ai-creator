"""Regression test: automatic publishing must remain paused by default."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("binance_square_publisher", ROOT / "src" / "binance_square_publisher.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class SharedEmergencyStopTest(unittest.TestCase):
    def test_shared_stop_reads_repository_variable(self):
        old = {name: os.environ.get(name) for name in ("NIC_SHARED_GITHUB_STOP", "GITHUB_REPOSITORY", "GITHUB_TOKEN")}
        try:
            os.environ["NIC_SHARED_GITHUB_STOP"] = "1"
            os.environ["GITHUB_REPOSITORY"] = "owner/repo"
            os.environ["GITHUB_TOKEN"] = "test-token"
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self): return b'{"value":"1"}'
            with patch.object(publisher.urllib.request, "urlopen", return_value=Response()) as request:
                self.assertTrue(publisher.github_emergency_stop_requested())
                self.assertIn("/actions/variables/NIC_EMERGENCY_STOP", request.call_args.args[0].full_url)
            class ResumeResponse(Response):
                def read(self): return b'{"value":"0"}'
            with patch.object(publisher.urllib.request, "urlopen", return_value=ResumeResponse()):
                self.assertFalse(publisher.github_emergency_stop_requested())
        finally:
            for name, value in old.items():
                if value is None: os.environ.pop(name, None)
                else: os.environ[name] = value

    def test_shared_stop_fails_closed_when_variable_cannot_be_read(self):
        old = {name: os.environ.get(name) for name in ("NIC_SHARED_GITHUB_STOP", "GITHUB_REPOSITORY", "GITHUB_TOKEN")}
        try:
            os.environ["NIC_SHARED_GITHUB_STOP"] = "1"
            os.environ["GITHUB_REPOSITORY"] = "owner/repo"
            os.environ["GITHUB_TOKEN"] = "test-token"
            with patch.object(publisher.urllib.request, "urlopen", side_effect=OSError("unavailable")):
                self.assertTrue(publisher.github_emergency_stop_requested())
        finally:
            for name, value in old.items():
                if value is None: os.environ.pop(name, None)
                else: os.environ[name] = value


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



    def test_emergency_stop_blocks_enabled_publisher_before_credentials_or_network(self):
        names = ("PUBLISHING_ENABLED", "NIC_EMERGENCY_STOP", "BINANCE_SQUARE_OPENAPI_KEY", "BINANCE_SQUARE_API_KEY")
        old = {name: os.environ.get(name) for name in names}
        old_result = publisher.RESULT_PATH
        try:
            os.environ["PUBLISHING_ENABLED"] = "true"
            os.environ["NIC_EMERGENCY_STOP"] = "1"
            os.environ.pop("BINANCE_SQUARE_OPENAPI_KEY", None)
            os.environ.pop("BINANCE_SQUARE_API_KEY", None)
            with tempfile.TemporaryDirectory() as directory:
                publisher.RESULT_PATH = Path(directory) / "publication_result.json"
                result = publisher.main()
                payload = json.loads(publisher.RESULT_PATH.read_text(encoding="utf-8"))
                self.assertEqual(result, 0)
                self.assertEqual(payload["status"], "PUBLISH_BLOCKED_EMERGENCY_STOP")
                self.assertEqual(payload["current_run_publication"], "NO_NEW_PUBLICATION")
                self.assertIsNone(payload["post_id"])
        finally:
            publisher.RESULT_PATH = old_result
            for name, value in old.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

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
        self.assertIn("steps.publication_authorization.outputs.authorized == 'true'", payload)
        self.assertIn("steps.publication_authorization.outputs.authorized == 'true'", publisher_step)
        self.assertNotIn("outputs.authorized == 'true' && false", payload + publisher_step)
        self.assertIn("PUBLISHING_ENABLED: 'true'", publisher_step)
        self.assertIn("current-cycle authorization", payload)
        self.assertIn("exact-draft hashes", publisher_step)
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


    def test_production_evidence_gate_runs_before_forecast_artifacts_are_staged(self):
        workflow = (ROOT / ".github" / "workflows" / "autonomous-market-creator.yml").read_text(encoding="utf-8")
        marker = "      - name: Persist Forecast Laboratory evidence ledgers"
        start = workflow.index(marker)
        end = workflow.find("\n      - name:", start + len(marker))
        step = workflow[start:] if end < 0 else workflow[start:end]
        gate = "python src/nic_evidence_reconciliation_gate.py"
        staging = "git add -- data/intelligence/nic_forecast_truth_ledger.jsonl"
        self.assertIn(gate, step)
        self.assertIn(staging, step)
        self.assertLess(step.index(gate), step.index(staging))
        self.assertIn("set -euo pipefail", step)


    def test_production_evidence_gate_rechecks_shared_main_after_successful_push(self):
        workflow = (ROOT / ".github" / "workflows" / "autonomous-market-creator.yml").read_text(encoding="utf-8")
        marker = "      - name: Persist Forecast Laboratory evidence ledgers"
        start = workflow.index(marker)
        end = workflow.find("\\n      - name:", start + len(marker))
        step = workflow[start:] if end < 0 else workflow[start:end]
        push = step.index("if git push origin HEAD:main; then")
        fetch = step.index("git fetch origin main", push)
        reset = step.index("git reset --hard origin/main", fetch)
        gate = step.index("python src/nic_evidence_reconciliation_gate.py", reset)
        success = step.index("Forecast evidence persisted and post-push main reconciled", gate)
        self.assertLess(push, fetch)
        self.assertLess(fetch, reset)
        self.assertLess(reset, gate)
        self.assertLess(gate, success)

if __name__ == "__main__":
    unittest.main()
