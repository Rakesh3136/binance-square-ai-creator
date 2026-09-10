"""Publish the validated draft to Binance Square through the Square OpenAPI.

This is the single publication adapter used by the autonomous workflow.
It deliberately uses the dedicated Square posting key only; generic Binance
trading API credentials are never accepted as a fallback.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
ANALYTICS = ROOT / "analytics"
PAYLOAD_PATH = LIVE / "publication_payload.json"
LOG_PATH = ANALYTICS / "publication_log.jsonl"
RESULT_PATH = LIVE / "publication_result.json"
ENDPOINT = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(message: str, code: str = "PUBLISH_FAILED", http_status: int | None = None) -> int:
    result = {
        "status": code,
        "message": message,
        "checked_at": now(),
        "endpoint": ENDPOINT,
        "post_id": None,
        "link": None,
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2


def append_log(row: dict) -> None:
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_text() -> str:
    if not PAYLOAD_PATH.exists():
        raise RuntimeError(f"publication payload is missing: {PAYLOAD_PATH}")
    data = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("publication payload must be a JSON object")

    text = data.get("text") or data.get("bodyTextOnly") or data.get("content")
    if not isinstance(text, str):
        raise RuntimeError("publication payload has no text/bodyTextOnly/content field")
    text = text.strip()
    if not text:
        raise RuntimeError("publication text is empty")
    if len(text) > 10000:
        raise RuntimeError(f"publication text is too long ({len(text)} characters)")
    return text


def publish(text: str, api_key: str) -> dict:
    body = json.dumps({"bodyTextOnly": text}, ensure_ascii=False).encode("utf-8")
    request = Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
            "User-Agent": "binance-square-ai-creator/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Binance returned non-JSON response: {raw[:300]}") from exc


def main() -> int:
    api_key = os.getenv("BINANCE_SQUARE_OPENAPI_KEY", "").strip()
    if not api_key:
        return fail(
            "BINANCE_SQUARE_OPENAPI_KEY is not configured. Create a dedicated Binance Square posting API key and store it as a GitHub Actions secret.",
            "PUBLISHER_NOT_CONFIGURED",
        )

    try:
        text = load_text()
        # A single request is intentional. Do not blindly retry a timeout because
        # Binance may have accepted the post even when the client cannot see the response.
        response = publish(text, api_key)
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            detail = str(exc)
        row = {
            "timestamp": now(),
            "status": "PUBLISH_FAILED",
            "post_id": None,
            "link": None,
            "error": f"HTTP {exc.code}: {detail}",
        }
        append_log(row)
        return fail(row["error"], "PUBLISH_FAILED", exc.code)
    except (URLError, TimeoutError) as exc:
        row = {
            "timestamp": now(),
            "status": "PUBLISH_UNKNOWN",
            "post_id": None,
            "link": None,
            "error": f"network result unknown: {exc}",
        }
        append_log(row)
        return fail(row["error"], "PUBLISH_UNKNOWN")
    except Exception as exc:
        row = {
            "timestamp": now(),
            "status": "PUBLISH_FAILED",
            "post_id": None,
            "link": None,
            "error": str(exc),
        }
        append_log(row)
        return fail(str(exc), "PUBLISH_FAILED")

    code = str(response.get("code", ""))
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    post_id = str(data.get("id") or data.get("contentId") or "").strip()

    if code != "000000" or not post_id:
        message = str(response.get("message") or f"Binance response code={code!r} without a post id")
        row = {
            "timestamp": now(),
            "status": "PUBLISH_REJECTED",
            "post_id": None,
            "link": None,
            "error": message,
            "api_code": code,
        }
        append_log(row)
        return fail(message, "PUBLISH_REJECTED")

    link = f"https://www.binance.com/square/post/{post_id}"
    row = {
        "timestamp": now(),
        "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "post_id": post_id,
        "link": link,
        "api_code": code,
        "text_length": len(text),
    }
    append_log(row)
    result = {
        "status": row["status"],
        "checked_at": now(),
        "post_id": post_id,
        "link": link,
        "api_code": code,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
