"""Regression tests for publisher duplicate-state telemetry."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import binance_square_publisher as publisher


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        publisher.LOG_PATH = root / "publication_log.jsonl"
        publisher.RESULT_PATH = root / "publication_result.json"
        publisher.LIVE = root
        stamp = datetime.now(timezone.utc).isoformat()
        existing = {
            "timestamp": stamp,
            "published_at": stamp,
            "status": "VERIFIED_PUBLISHED",
            "post_id": "370437640100071",
            "canonical_post_id": "370437640100071",
            "link": "https://www.binance.com/square/post/370437640100071",
            "symbol": "NFP",
            "category": "technical_setup",
            "text": "Existing verified post",
        }
        publisher.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        publisher.LOG_PATH.write_text(json.dumps(existing) + "\n", encoding="utf-8")

        reason, match = publisher.duplicate_match(
            "Existing verified post", "NFP", "technical_setup", {}, {}
        )
        assert reason.startswith("exact_text_duplicate_within_"), reason
        assert match.get("post_id") == "370437640100071"

        rc = publisher.skip(
            "Duplicate publication blocked", "PUBLISH_BLOCKED_DUPLICATE",
            "NFP", "technical_setup", match
        )
        assert rc == 0
        result = json.loads(publisher.RESULT_PATH.read_text(encoding="utf-8"))
        assert result["post_id"] is None
        assert result["current_run_publication"] == "NO_NEW_PUBLICATION"
        assert result["publication_state"] == "CURRENT_RUN_NO_NEW_PUBLICATION — EXISTING_POST_VERIFIED"
        assert result["existing_publication"]["canonical_post_id"] == "370437640100071"
        assert result["existing_publication"]["verified"] is True

    print("PUBLISHER_DUPLICATE_TELEMETRY_TEST_OK")


if __name__ == "__main__":
    main()
