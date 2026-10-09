"""Regression test: automatic publishing must remain paused by default."""
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


if __name__ == "__main__":
    unittest.main()
