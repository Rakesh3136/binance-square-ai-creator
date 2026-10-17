"""Strict verification contract for Binance Square Write-to-Earn reward events.

A reward can influence creator-learning only when it is positive, explicitly
verified, linked to one canonical post ID, timestamped, and backed by a
source reference plus a SHA-256/excerpt hash. Views and notifications alone
are never sufficient.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

VERIFIED_REWARD_STATUSES = {"PAID_VERIFIED", "REWARD_VERIFIED", "VERIFIED_PAID_REWARD"}
POST_ID_RE = re.compile(r"^[0-9]{6,}$")


def parse_aware_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def canonical_post_id(row: dict[str, Any]) -> str:
    raw = str(row.get("canonical_post_id") or row.get("post_id") or row.get("publication_id") or "").strip()
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    elif raw.startswith("http://") or raw.startswith("https://"):
        raw = urlparse(raw).path.rstrip("/").split("/")[-1]
    return raw if POST_ID_RE.fullmatch(raw) else ""


def has_hashed_timestamped_evidence(row: dict[str, Any]) -> bool:
    refs = row.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        source = str(ref.get("source_id") or ref.get("url") or "").strip()
        digest = str(ref.get("sha256") or ref.get("excerpt_hash") or "").strip().lower()
        observed = parse_aware_time(ref.get("observed_at"))
        if source and re.fullmatch(r"[0-9a-f]{64}", digest) and observed is not None:
            return True
    return False


def reward_event_rejection_reasons(row: dict[str, Any]) -> list[str]:
    """Return stable, non-sensitive reasons a reward event is not admissible."""
    if not isinstance(row, dict):
        return ["event_not_object"]
    reasons: list[str] = []
    if row.get("verified") is not True:
        reasons.append("verified_flag_missing")
    status = str(row.get("reward_status") or row.get("detail_status") or "").strip().upper()
    if status not in VERIFIED_REWARD_STATUSES:
        reasons.append("reward_status_not_paid_verified")
    if not str(row.get("event_id") or "").strip():
        reasons.append("event_id_missing")
    if not canonical_post_id(row):
        reasons.append("canonical_post_id_missing_or_invalid")
    if str(row.get("currency") or "").strip().upper() != "USDC":
        reasons.append("currency_not_usdc")
    try:
        amount = float(row.get("reward_amount_usdc"))
        if not math.isfinite(amount) or amount <= 0:
            reasons.append("reward_amount_not_positive_finite")
    except (TypeError, ValueError):
        reasons.append("reward_amount_missing_or_invalid")
    if parse_aware_time(row.get("observed_at")) is None:
        reasons.append("observed_at_missing_or_timezone_naive")
    if parse_aware_time(row.get("verified_at")) is None:
        reasons.append("verified_at_missing_or_timezone_naive")
    if not has_hashed_timestamped_evidence(row):
        reasons.append("hashed_timestamped_evidence_ref_missing")
    return reasons


def is_verified_reward_event(row: dict[str, Any]) -> bool:
    return not reward_event_rejection_reasons(row)
