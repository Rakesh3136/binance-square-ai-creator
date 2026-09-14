"""Binance Square publisher with fail-closed live publication proof.

Creator 9.2 rule: a cycle is not considered published unless Binance's
OpenAPI response yields a concrete canonical post id. Unknown/504 responses
are never converted into a published state and are never retried blindly.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
ANALYTICS = ROOT / "analytics"
PAYLOAD_PATH = LIVE / "publication_payload.json"
LOG_PATH = ANALYTICS / "publication_log.jsonl"
RESULT_PATH = LIVE / "publication_result.json"
CONTEXT_PATH = LIVE / "publication_context.json"
FROZEN_PATH = LIVE / "authoritative_opportunity.json"
VISUAL = LIVE / "visual.png"
ENDPOINT = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
IMAGE_LANES = {
    "crypto_meme", "market_meme", "trader_humor", "technical_setup",
    "capital_flow_long", "capital_flow_short", "result_followup",
    "research_radar", "news", "breaking_news", "news_and_macro",
}
DUPLICATE_HOURS = float(os.getenv("PUBLISH_DUPLICATE_HOURS", "6"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def canonical_post_id(value) -> str:
    """Accept only a concrete Binance Square post identifier."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    # Do not invent ids from arbitrary text. Accept numeric ids and the
    # documented id-like strings returned by Square, after URL cleanup.
    raw = raw.rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    raw = raw.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw):
        return raw
    return ""


def clean_symbol(value) -> str:
    symbol = re.sub(r"USDT$", "", str(value or "").upper().replace("$", "").strip())
    return symbol if re.fullmatch(r"[A-Z0-9]{1,15}", symbol) else ""


def fail(message: str, code: str) -> int:
    result = {
        "status": code,
        "message": message,
        "checked_at": now(),
        "endpoint": ENDPOINT,
        "post_id": None,
        "link": None,
        "publication_proof": "none",
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2


def text_payload() -> str:
    data = load(PAYLOAD_PATH)
    text = str(data.get("text") or data.get("bodyTextOnly") or data.get("content") or "").strip()
    if not text:
        raise RuntimeError("publication text is empty")
    if len(text) > 10000:
        raise RuntimeError(f"publication text is too long ({len(text)})")
    return text


def recent_rows() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    accepted = {
        "PUBLISHED_AUTONOMOUSLY",
        "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "VERIFIED_PUBLISHED",
    }
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines()[-300:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and str(row.get("status") or "") in accepted:
            rows.append(row)
    return rows


def duplicate_reason(text: str, symbol: str, category: str) -> str:
    target = clean_symbol(symbol)
    now_dt = datetime.now(timezone.utc)
    for row in reversed(recent_rows()):
        row_symbol = clean_symbol(row.get("symbol") or row.get("selected_lane_symbol"))
        timestamp = row.get("published_at") or row.get("timestamp") or ""
        try:
            age = now_dt - datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except Exception:
            continue
        if age > timedelta(hours=DUPLICATE_HOURS):
            continue
        old_text = str(row.get("text") or row.get("post") or row.get("content") or "").strip()
        old_category = str(row.get("category") or "").lower()
        if old_text and old_text == text.strip():
            return f"exact_text_duplicate_within_{DUPLICATE_HOURS:g}h"
        if (
            target and row_symbol == target and old_category == str(category or "").lower()
            and not any(k in text.lower() for k in ("result", "outcome", "invalidated", "follow-up", "follow up"))
        ):
            return f"same_asset_and_category_within_{DUPLICATE_HOURS:g}h"
    return ""


def append(row: dict) -> None:
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_verified_result(result: dict) -> dict:
    post_id = canonical_post_id(result.get("post_id") or result.get("id") or result.get("contentId"))
    status = str(result.get("status") or "")
    if status == "PUBLISHED_UNKNOWN":
        raise RuntimeError("Binance accepted/submitted the request without returning a post id; publication remains unverified")
    if status != "PUBLISHED_VERIFIED_BY_API_RESPONSE" or not post_id:
        raise RuntimeError(result.get("error") or "publication response did not contain a verified post id")
    link = str(result.get("link") or result.get("shareLink") or "").strip()
    if not link:
        link = f"https://www.binance.com/square/post/{post_id}"
    return {
        "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "post_id": post_id,
        "link": link,
        "publication_proof": "binance_openapi_response_post_id",
        "image_url": result.get("image_url"),
    }


def main() -> int:
    # The workflow historically exposed BINANCE_SQUARE_API_KEY while the
    # adapter consumed BINANCE_SQUARE_OPENAPI_KEY. Support the existing secret
    # name without weakening the fail-closed publication proof.
    key = (os.getenv("BINANCE_SQUARE_OPENAPI_KEY") or os.getenv("BINANCE_SQUARE_API_KEY") or "").strip()
    if not key:
        return fail("BINANCE_SQUARE_OPENAPI_KEY/BINANCE_SQUARE_API_KEY is not configured", "PUBLISHER_NOT_CONFIGURED")

    try:
        text = text_payload()
        context = load(CONTEXT_PATH)
        frozen = load(FROZEN_PATH)
        symbol = clean_symbol(context.get("symbol") or frozen.get("symbol"))
        category = str(context.get("category") or frozen.get("category") or "").lower()
        if not symbol:
            raise RuntimeError("publication symbol is missing")

        duplicate = duplicate_reason(text, symbol, category)
        if duplicate:
            append({
                "timestamp": now(), "status": "PUBLISH_BLOCKED_DUPLICATE", "post_id": None,
                "link": None, "symbol": symbol, "category": category, "text": text, "reason": duplicate,
            })
            return fail(f"Duplicate publication blocked: {duplicate}", "PUBLISH_BLOCKED_DUPLICATE")

        use_image = VISUAL.exists() and VISUAL.stat().st_size > 10000 and (
            category in IMAGE_LANES or bool(context.get("visual_requested"))
        )

        if use_image:
            process = subprocess.run(
                ["node", str(ROOT / "src/square_image_publisher.mjs"), str(VISUAL), text],
                env={**os.environ, "BINANCE_SQUARE_OPENAPI_KEY": key},
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            if process.stdout.strip():
                print(process.stdout)
            if process.returncode != 0:
                raise RuntimeError(process.stderr.strip() or "image publisher failed")
            lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError("image publisher returned no result")
            api_result = json.loads(lines[-1])
        else:
            import urllib.request
            body = json.dumps({"bodyTextOnly": text}, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                ENDPOINT, data=body, method="POST",
                headers={
                    "X-Square-OpenAPI-Key": key,
                    "Content-Type": "application/json",
                    "clienttype": "binanceSkill",
                    "User-Agent": "binance-square-ai-creator/1.4",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                api = json.loads(response.read().decode("utf-8", errors="replace"))
            code = str(api.get("code", ""))
            data = api.get("data") if isinstance(api.get("data"), dict) else {}
            api_result = {
                "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE" if code == "000000" and canonical_post_id(data.get("id") or data.get("contentId")) else "PUBLISH_REJECTED",
                "post_id": data.get("id") or data.get("contentId"),
                "link": data.get("shareLink") or "",
                "api_code": code,
                "error": api.get("message"),
            }

        verified = build_verified_result(api_result)
    except Exception as exc:
        append({
            "timestamp": now(), "status": "PUBLISH_FAILED", "post_id": None,
            "link": None, "error": str(exc), "publication_proof": "none",
        })
        return fail(str(exc), "PUBLISH_FAILED")

    post_id = verified["post_id"]
    link = verified["link"]
    row = {
        "timestamp": now(), "published_at": now(), "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "post_id": post_id, "canonical_post_id": post_id, "link": link,
        "text": text, "text_length": len(text), "symbol": symbol, "category": category,
        "experiment_id": str(context.get("experiment_id") or frozen.get("experiment_id") or ""),
        "reference_price": frozen.get("reference_price") or context.get("reference_price"),
        "trigger": frozen.get("trigger") or frozen.get("entry"),
        "invalidation": frozen.get("invalidation"),
        "targets": frozen.get("targets") or frozen.get("take_profit") or [],
        "visual_attached": use_image, "visual_path": str(VISUAL) if use_image else None,
        "editorial_style": str(context.get("editorial_style") or ""),
        "publication_id_verified": True,
        "publication_proof": "binance_openapi_response_post_id",
    }
    append(row)
    result = {
        "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE", "checked_at": now(),
        "post_id": post_id, "canonical_post_id": post_id, "link": link,
        "symbol": symbol, "category": category, "visual_attached": use_image,
        "id_verification": "verified", "publication_proof": "binance_openapi_response_post_id",
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
