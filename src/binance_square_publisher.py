"""Binance Square publisher with explicit verified/submitted/skipped states."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
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
WTE_PATH = LIVE / "write_to_earn_eligibility.json"
ATTRIBUTION_LOG_PATH = ANALYTICS / "publication_attribution.jsonl"
VISUAL = LIVE / "visual.png"
ENDPOINT = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
NO_IMAGE_LANES = {"education", "commentary", "community", "text_only"}
DUPLICATE_HOURS = float(os.getenv("PUBLISH_DUPLICATE_HOURS", "6"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def canonical_post_id(v) -> str:
    raw = str(v or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0].strip()
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw) else ""


def clean_symbol(v) -> str:
    s = re.sub(r"USDT$", "", str(v or "").upper().replace("$", "").strip())
    return s if re.fullmatch(r"[A-Z0-9]{1,15}", s) else ""


def fail(message: str, code: str, exit_code: int = 2) -> int:
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
    return exit_code


def skip(
    message: str,
    code: str,
    symbol: str = "",
    category: str = "",
    existing: dict | None = None,
) -> int:
    existing = existing if isinstance(existing, dict) else {}
    existing_id = canonical_post_id(
        existing.get("canonical_post_id") or existing.get("post_id") or existing.get("link")
    )
    existing_link = str(existing.get("link") or "").strip() or (
        f"https://www.binance.com/square/post/{existing_id}" if existing_id else None
    )
    is_existing_verified = code == "PUBLISH_BLOCKED_DUPLICATE" and bool(existing_id)
    result = {
        "status": code,
        "message": message,
        "checked_at": now(),
        "endpoint": ENDPOINT,
        # post_id is reserved for a publication created/identified by THIS run.
        "post_id": None,
        "link": None,
        "symbol": symbol or None,
        "category": category or None,
        "publication_proof": "none",
        "current_run_publication": "NO_NEW_PUBLICATION" if code == "PUBLISH_BLOCKED_DUPLICATE" else code,
        "publication_state": (
            "CURRENT_RUN_NO_NEW_PUBLICATION — EXISTING_POST_VERIFIED"
            if is_existing_verified
            else code
        ),
        "existing_publication": {
            "verified": is_existing_verified,
            "canonical_post_id": existing_id or None,
            "link": existing_link,
            "status": str(existing.get("status") or "") or None,
            "published_at": existing.get("published_at") or existing.get("timestamp"),
        },
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
def text_payload() -> str:
    d = load(PAYLOAD_PATH)
    t = str(d.get("text") or d.get("bodyTextOnly") or d.get("content") or "").strip()
    if not t:
        raise RuntimeError("publication text is empty")
    if len(t) > 10000:
        raise RuntimeError(f"publication text is too long ({len(t)})")
    return t


def recent_rows():
    if not LOG_PATH.exists():
        return []
    accepted = {
        "PUBLISHED_AUTONOMOUSLY",
        "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "VERIFIED_PUBLISHED",
        "PUBLISHED_SUBMITTED_504",
    }
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines()[-300:]:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict) and str(r.get("status") or "") in accepted:
            rows.append(r)
    return rows


def duplicate_match(text: str, symbol: str, category: str, context: dict, frozen: dict):
    target = clean_symbol(symbol)
    current_direction = str(
        context.get("direction")
        or (context.get("prediction") or {}).get("direction")
        or frozen.get("direction")
        or (frozen.get("prediction") or {}).get("direction")
        or ""
    ).upper()
    current_trigger = context.get("entry_trigger") or frozen.get("entry_trigger") or frozen.get("trigger") or frozen.get("entry")
    current_invalidation = context.get("sl") or frozen.get("sl") or frozen.get("invalidation")
    now_dt = datetime.now(timezone.utc)
    for row in reversed(recent_rows()):
        rs = clean_symbol(row.get("symbol") or row.get("selected_lane_symbol"))
        row_category = str(row.get("category") or row.get("content_category") or "").lower()
        try:
            stamp = str(row.get("published_at") or row.get("timestamp") or "")
            age = now_dt - datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except Exception:
            continue
        if age > timedelta(hours=DUPLICATE_HOURS):
            continue
        old = str(row.get("text") or row.get("post") or row.get("content") or "").strip()
        if old and old == text.strip():
            return f"exact_text_duplicate_within_{DUPLICATE_HOURS:g}h", row

        same_asset_category = target and rs == target and row_category == str(category or "").lower()
        if not same_asset_category:
            continue

        old_direction = str(row.get("direction") or row.get("side") or "").upper()
        old_trigger = row.get("trigger") or row.get("entry_trigger")
        old_invalidation = row.get("invalidation") or row.get("sl")

        # Signal/setup posts may revisit the same asset when the decision map
        # changed. Block only a genuinely repeated setup, not every same-asset
        # post. Legacy rows without a stored direction/setup are not enough to
        # classify a new conditional thesis as a duplicate.
        if current_direction and old_direction:
            same_direction = current_direction == old_direction
            same_trigger = str(current_trigger) == str(old_trigger) if current_trigger is not None and old_trigger is not None else True
            same_invalidation = str(current_invalidation) == str(old_invalidation) if current_invalidation is not None and old_invalidation is not None else True
            if same_direction and same_trigger and same_invalidation:
                return f"same_asset_category_and_setup_within_{DUPLICATE_HOURS:g}h", row

        # For non-signal posts, retain the conservative old cooldown.
        if not current_direction and not old_direction and not any(k in text.lower() for k in ("result", "outcome", "invalidated", "follow-up", "follow up")):
            return f"same_asset_and_category_within_{DUPLICATE_HOURS:g}h", row

    return ""


def duplicate_reason(text: str, symbol: str, category: str, context: dict, frozen: dict) -> str:
    reason, _ = duplicate_match(text, symbol, category, context, frozen)
    return reason

def append(row: dict) -> None:
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as h:
        h.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_attribution(row: dict) -> None:
    """Persist a durable post-to-monetization lineage event.

    This records what was actually published and what attribution mechanism was
    present. It deliberately does not manufacture reader trades or revenue.
    """
    ANALYTICS.mkdir(parents=True, exist_ok=True)
    with ATTRIBUTION_LOG_PATH.open("a", encoding="utf-8") as h:
        h.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    key = (os.getenv("BINANCE_SQUARE_OPENAPI_KEY") or os.getenv("BINANCE_SQUARE_API_KEY") or "").strip()
    if not key:
        return fail("BINANCE_SQUARE_OPENAPI_KEY/BINANCE_SQUARE_API_KEY is not configured", "PUBLISHER_NOT_CONFIGURED")

    try:
        text = text_payload()
        context = load(CONTEXT_PATH)
        frozen = load(FROZEN_PATH)
        symbol = clean_symbol(
            context.get("symbol")
            or context.get("primary_symbol")
            or frozen.get("symbol")
            or frozen.get("symbol_usdt")
        )
        category = str(
            context.get("category")
            or context.get("content_category")
            or frozen.get("category")
            or frozen.get("content_category")
            or ""
        ).lower()
        if not symbol:
            raise RuntimeError("publication symbol is missing")

        # The W2E gate is authoritative. Never publish when it says ineligible.
        wte = load(WTE_PATH)
        if wte and wte.get("eligible") is False:
            reason = str(wte.get("reason") or "w2e eligibility gate rejected publication")
            append({
                "timestamp": now(),
                "status": "PUBLISH_SKIPPED_WTE_INELIGIBLE",
                "post_id": None,
                "link": None,
                "symbol": symbol,
                "category": category,
                "reason": reason,
                "publication_proof": "none",
            })
            return skip(f"Publication skipped by W2E eligibility gate: {reason}", "PUBLISH_SKIPPED_WTE_INELIGIBLE", symbol, category)

        dup, existing = duplicate_match(text, symbol, category, context, frozen)
        if dup:
            existing_id = canonical_post_id(
                existing.get("canonical_post_id") or existing.get("post_id") or existing.get("link")
            )
            existing_link = str(existing.get("link") or "").strip() or (
                f"https://www.binance.com/square/post/{existing_id}" if existing_id else None
            )
            append({
                "timestamp": now(),
                "status": "PUBLISH_BLOCKED_DUPLICATE",
                "post_id": None,
                "link": None,
                "existing_post_id": existing_id or None,
                "existing_post_link": existing_link,
                "existing_publication_status": str(existing.get("status") or "") or None,
                "existing_publication_verified_at": existing.get("published_at") or existing.get("timestamp"),
                "symbol": symbol,
                "category": category,
                "text": text,
                "reason": dup,
                "publication_proof": "existing_verified_publication_log",
            })
            # Duplicate protection is an intentional safety skip, not a workflow failure.
            # Keep the current run's post_id null; expose the verified prior post separately.
            return skip(
                f"Duplicate publication blocked: {dup}",
                "PUBLISH_BLOCKED_DUPLICATE",
                symbol,
                category,
                existing,
            )

        visual_requested = bool(
            context.get("visual_requested")
            or context.get("visual_required")
            or context.get("visual_verified")
            or context.get("tradingview_verified")
            or (context.get("visual_decision") or {}).get("required")
        )
        require_image = visual_requested or category not in NO_IMAGE_LANES
        use_image = VISUAL.exists() and VISUAL.stat().st_size > 10000 and require_image
        if require_image and not use_image:
            raise RuntimeError(f"Required TradingView visual is missing or too small for {symbol}: {VISUAL}")

        if use_image:
            p = subprocess.run(
                ["node", str(ROOT / "src/square_image_publisher.mjs"), str(VISUAL), text],
                env={**os.environ, "BINANCE_SQUARE_OPENAPI_KEY": key},
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if p.stdout.strip():
                print(p.stdout)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.strip() or "image publisher failed")
            lines = [x.strip() for x in p.stdout.splitlines() if x.strip()]
            if not lines:
                raise RuntimeError("image publisher returned no result")
            api_result = json.loads(lines[-1])
        else:
            body = json.dumps({"bodyTextOnly": text}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                ENDPOINT,
                data=body,
                method="POST",
                headers={
                    "X-Square-OpenAPI-Key": key,
                    "Content-Type": "application/json",
                    "clienttype": "binanceSkill",
                    "User-Agent": "binance-square-ai-creator/1.6",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    api = json.loads(response.read().decode("utf-8", errors="replace"))
            except urllib.error.HTTPError as e:
                if e.code == 504:
                    api = {"code": "504", "data": {}, "message": "submitted without post id"}
                else:
                    raise
            code = str(api.get("code", ""))
            data = api.get("data") if isinstance(api.get("data"), dict) else {}
            pid = canonical_post_id(data.get("id") or data.get("contentId"))
            api_result = {
                "status": "PUBLISHED_VERIFIED_BY_API_RESPONSE" if code == "000000" and pid else ("PUBLISHED_SUBMITTED_504" if code == "504" else "PUBLISH_REJECTED"),
                "post_id": pid or None,
                "link": data.get("shareLink") or "",
                "api_code": code,
                "error": api.get("message"),
            }

        status = str(api_result.get("status") or "")
        if status == "PUBLISHED_VERIFIED_BY_API_RESPONSE":
            post_id = canonical_post_id(api_result.get("post_id") or api_result.get("id"))
            if not post_id:
                raise RuntimeError("Binance response claimed success without a canonical post id")
            link = str(api_result.get("link") or api_result.get("shareLink") or "").strip() or f"https://www.binance.com/square/post/{post_id}"
            proof = "binance_openapi_response_post_id"
            exit_code = 0
        elif status == "PUBLISHED_SUBMITTED_504":
            post_id = ""
            link = ""
            proof = "binance_content_add_http_504_submission_unknown"
            exit_code = 0
        else:
            raise RuntimeError(api_result.get("error") or "Binance rejected publication")
    except Exception as exc:
        append({
            "timestamp": now(),
            "status": "PUBLISH_FAILED",
            "post_id": None,
            "link": None,
            "error": str(exc),
            "publication_proof": "none",
        })
        return fail(str(exc), "PUBLISH_FAILED")

    row = {
        "timestamp": now(),
        "published_at": now(),
        "status": status,
        "post_id": post_id or None,
        "canonical_post_id": post_id or None,
        "link": link or None,
        "text": text,
        "text_length": len(text),
        "symbol": symbol,
        "category": category,
        "direction": str(
            context.get("direction")
            or (context.get("prediction") or {}).get("direction")
            or frozen.get("direction")
            or (frozen.get("prediction") or {}).get("direction")
            or ""
        ).upper(),
        "experiment_id": str(context.get("experiment_id") or frozen.get("experiment_id") or ""),
        "reference_price": frozen.get("reference_price") or context.get("reference_price"),
        "trigger": frozen.get("trigger") or frozen.get("entry"),
        "invalidation": frozen.get("invalidation"),
        "targets": frozen.get("targets") or frozen.get("take_profit") or [],
        "visual_attached": use_image,
        "visual_path": str(VISUAL) if use_image else None,
        "visual_url": api_result.get("image_url"),
        "editorial_style": str(context.get("editorial_style") or ""),
        "publication_id_verified": bool(post_id),
        "publication_proof": proof,
        "monetization": {
            "wte_eligible": bool(wte.get("eligible")) if isinstance(wte, dict) else None,
            "required_attribution": bool(wte.get("required_attribution")) if isinstance(wte, dict) else None,
            "cashtag": str(wte.get("cashtag") or f"${symbol}") if isinstance(wte, dict) else f"${symbol}",
            "has_primary_cashtag": bool(wte.get("has_primary_cashtag")) if isinstance(wte, dict) else None,
            "verified_widget": wte.get("verified_widget") if isinstance(wte, dict) else False,
            "revenue_verified": False,
            "qualified_trade_count": None,
            "reward_amount_usdc": None,
            "status": "AWAITING_VERIFIED_READER_ACTIVITY",
        },
    }
    append(row)
    append_attribution({
        "recorded_at": row["published_at"],
        "post_id": post_id or None,
        "canonical_post_id": post_id or None,
        "published_at": row["published_at"],
        "symbol": symbol,
        "category": category,
        "direction": row["direction"],
        "experiment_id": row["experiment_id"],
        "reference_price": row["reference_price"],
        "trigger": row["trigger"],
        "invalidation": row["invalidation"],
        "targets": row["targets"],
        "cashtag": row["monetization"]["cashtag"],
        "has_primary_cashtag": row["monetization"]["has_primary_cashtag"],
        "verified_widget": row["monetization"]["verified_widget"],
        "visual_attached": use_image,
        "visual_url": api_result.get("image_url"),
        "publication_proof": proof,
        "revenue_verified": False,
        "qualified_trade_count": None,
        "reward_amount_usdc": None,
        "status": "AWAITING_VERIFIED_READER_ACTIVITY",
        "lineage_policy": "exact_post_id_first; revenue_only_from_explicit_verified_fields",
    })
    result = {
        "status": status,
        "checked_at": now(),
        "post_id": post_id or None,
        "canonical_post_id": post_id or None,
        "link": link or None,
        "symbol": symbol,
        "category": category,
        "visual_attached": use_image,
        "visual_url": api_result.get("image_url"),
        "id_verification": "verified" if post_id else "unavailable",
        "publication_proof": proof,
        "experiment_id": row["experiment_id"],
        "cashtag": row["monetization"]["cashtag"],
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
