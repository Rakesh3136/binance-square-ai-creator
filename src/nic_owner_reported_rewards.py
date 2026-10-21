"""Owner-reported Binance Square reward evidence, kept separate from verified payouts.

Rows are useful for account-owner-directed learning but are never described as
independently verified revenue. Required JSONL fields:
event_id, post_id, reward_amount_usdc, currency="USDC", reported_at (timezone
aware ISO-8601), report_source="ACCOUNT_OWNER_REPORTED",
verification_status="OWNER_REPORTED".
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OWNER_REPORTED_REWARDS = ROOT / "analytics" / "wte_owner_reported_reward_events.jsonl"


def canonical_post_id(row: dict) -> str:
    raw = str(row.get("post_id") or row.get("canonical_post_id") or "").strip()
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    elif raw.startswith(("http://", "https://")):
        raw = urlparse(raw).path.rstrip("/").split("/")[-1]
    return raw if raw.isdigit() and len(raw) >= 6 else ""


def valid_owner_report(row: dict) -> bool:
    if not isinstance(row, dict):
        return False
    if not str(row.get("event_id") or "").strip():
        return False
    if not canonical_post_id(row):
        return False
    if str(row.get("currency") or "").strip().upper() != "USDC":
        return False
    if str(row.get("report_source") or "") != "ACCOUNT_OWNER_REPORTED":
        return False
    if str(row.get("verification_status") or "") != "OWNER_REPORTED":
        return False
    try:
        amount = float(row.get("reward_amount_usdc"))
        if not math.isfinite(amount) or amount <= 0:
            return False
    except (TypeError, ValueError):
        return False
    try:
        stamp = datetime.fromisoformat(str(row.get("reported_at") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return False
    except ValueError:
        return False
    return True


def load_owner_reported_rewards(path: Path = OWNER_REPORTED_REWARDS) -> dict[str, dict]:
    """Return post-level sums and event counts after strict validation/deduplication."""
    by_post = defaultdict(lambda: {"amount_usdc": 0.0, "event_count": 0, "event_ids": [], "content_metadata": {}})
    seen = set()
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not valid_owner_report(row):
            continue
        event_id = str(row["event_id"]).strip()
        if event_id in seen:
            continue
        seen.add(event_id)
        post_id = canonical_post_id(row)
        bucket = by_post[post_id]
        bucket["amount_usdc"] += float(row["reward_amount_usdc"])
        bucket["event_count"] += 1
        bucket["event_ids"].append(event_id)
        metadata = row.get("content_metadata")
        if isinstance(metadata, dict) and not bucket["content_metadata"]:
            allowed = ("content_lane", "content_format", "hook_type", "summary", "owner_reported_views", "public_post_url", "creator_origin")
            bucket["content_metadata"] = {key: metadata[key] for key in allowed if metadata.get(key) not in (None, "")}
    return {post: {"amount_usdc": round(v["amount_usdc"], 8), "event_count": v["event_count"], "event_ids": v["event_ids"], "content_metadata": v["content_metadata"]} for post, v in by_post.items()}
