"""Validate observed Binance Square Write-to-Earn leaderboard rows.

This is an evidence-ingestion boundary, not a scraper or payout verifier.
Never infer leaderboard amounts from public post metrics or creator claims.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "intelligence" / "wte_leaderboard_observations.json"
DEFAULT_OUTPUT = ROOT / "data" / "intelligence" / "wte_leaderboard_observed.json"
OFFICIAL_WTE_HOSTS = {"www.binance.com", "binance.com"}
OFFICIAL_WTE_PATH = re.compile(r"^/(?:en/)?square/(?:WriteToEarn|writetoearn)/?$", re.I)


def _timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc).isoformat()


def _official_wte_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_WTE_HOSTS:
        return None
    if not OFFICIAL_WTE_PATH.fullmatch(parsed.path):
        return None
    return value.strip().split("#", 1)[0]


def _profile_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_WTE_HOSTS
            or not re.search(r"/square/profile/[^/?#]+", parsed.path, re.I)):
        return None
    return value.strip().split("#", 1)[0]


def normalize_observations(payload: object, now: datetime | None = None) -> dict:
    """Normalize only explicitly observed rows; reject malformed evidence, never guess."""
    now = now or datetime.now(timezone.utc)
    rows = payload.get("entries", []) if isinstance(payload, dict) else []
    accepted, rejected = [], []
    if not isinstance(rows, list):
        rows = []
        rejected.append({"index": None, "reason": "entries_must_be_a_list"})

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            rejected.append({"index": index, "reason": "entry_must_be_an_object"})
            continue
        creator = str(row.get("creator") or "").strip()
        source_url = _official_wte_url(row.get("source_url"))
        observed_at = _timestamp(row.get("observed_at"))
        period_start = _timestamp(row.get("period_start"))
        period_end = _timestamp(row.get("period_end"))
        amount = row.get("displayed_amount")
        currency = str(row.get("currency") or "").strip().upper()
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        if not creator:
            reason = "creator_required"
        elif not source_url:
            reason = "official_write_to_earn_source_url_required"
        elif not observed_at or not period_start or not period_end:
            reason = "valid_timezone_aware_observed_at_and_period_required"
        elif datetime.fromisoformat(period_start) > datetime.fromisoformat(period_end):
            reason = "period_start_after_period_end"
        elif datetime.fromisoformat(observed_at) > now.astimezone(timezone.utc):
            reason = "observation_time_in_future"
        elif isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            reason = "displayed_amount_must_be_nonnegative_number"
        elif currency not in {"USDC", "USD"}:
            reason = "unsupported_or_missing_currency"
        elif not evidence_ref:
            reason = "evidence_ref_required"
        else:
            reason = None
        if reason:
            rejected.append({"index": index, "creator": creator or None, "reason": reason})
            continue
        profile = _profile_url(row.get("creator_profile_url"))
        rank = row.get("rank")
        accepted.append({
            "creator": creator[:160],
            "creator_profile_url": profile,
            "rank": rank if isinstance(rank, int) and not isinstance(rank, bool) and rank > 0 else None,
            "displayed_amount": float(amount),
            "currency": currency,
            "period_start": period_start,
            "period_end": period_end,
            "observed_at": observed_at,
            "source_url": source_url,
            "evidence_ref": evidence_ref[:500],
            "evidence_type": "OBSERVED_WRITE_TO_EARN_LEADERBOARD_ROW",
            "status": "OBSERVED_LEADERBOARD_ENTRY_NOT_OWN_PAYOUT",
            "independently_verified_payment": False,
            "public_metrics_used_as_earnings": False,
        })

    return {
        "schema": "NIC-WTE-LEADERBOARD-OBSERVATIONS-1.0",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "status": "OBSERVATIONS_NORMALIZED" if accepted else "NO_VALID_OBSERVATIONS",
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "entries": accepted,
        "rejected": rejected,
        "policy": {
            "amounts_are_observed_display_values_not_independently_verified_payouts": True,
            "public_views_or_engagement_never_substitute_for_leaderboard_evidence": True,
            "missing_creator_profile_url_is_unknown_not_invented": True,
        },
    }


def main() -> int:
    payload = json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))
    result = normalize_observations(payload)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "accepted_count", "rejected_count")}, indent=2))
    return 0 if result["rejected_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
