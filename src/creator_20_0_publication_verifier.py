"""Durable Binance Square publication truth verifier."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"
RESULT = LIVE / "publication_result.json"


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def canonical_post_id(v):
    raw = str(v or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw) else ""


def read_publications():
    path = ANALYTICS / "publication_log.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            pass
    return rows


def verified_status(status: str) -> bool:
    return status in {
        "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "VERIFIED_PUBLISHED",
        "PUBLISHED_AUTONOMOUSLY",
    }


def main():
    now = datetime.now(timezone.utc).isoformat()
    rows = read_publications()
    result_file = read_json(RESULT, {}) or {}

    result_id = canonical_post_id(
        result_file.get("canonical_post_id") or result_file.get("post_id")
    )

    matched_log = None
    if result_id:
        for row in reversed(rows):
            candidate = canonical_post_id(
                row.get("canonical_post_id") or row.get("post_id")
            )
            if candidate == result_id:
                matched_log = row
                break

    latest_verified = None
    for row in reversed(rows):
        rid = canonical_post_id(row.get("canonical_post_id") or row.get("post_id"))
        status = str(row.get("status") or "")
        if rid and verified_status(status) and row.get("publication_id_verified") is not False:
            latest_verified = row
            break

    latest = rows[-1] if rows else None
    latest_id = canonical_post_id(
        latest.get("canonical_post_id") or latest.get("post_id")
    ) if latest else ""

    # Preferred proof: the publisher result and its durable log record agree.
    if result_id and matched_log:
        log_status = str(matched_log.get("status") or "")
        log_id = canonical_post_id(
            matched_log.get("canonical_post_id") or matched_log.get("post_id")
        )
        if verified_status(log_status) and log_id == result_id and matched_log.get("publication_id_verified") is not False:
            truth_state = "VERIFIED_PUBLISHED"
            proof = "publisher result post_id matches a durable publication-log record carrying verified API-response proof"
            proof_source = "publisher_result_plus_publication_log"
        else:
            truth_state = "ATTEMPTED_NOT_VERIFIED"
            proof = "publisher result contains a post_id, but the matching durable log record is not verified"
            proof_source = "publisher_result_conflict"
    # Recovery path for the observed failure mode: the durable publication log
    # itself was written by the publisher immediately after a verified Binance
    # API response, while publication_result.json was empty/missing later.
    elif latest_verified:
        durable_id = canonical_post_id(
            latest_verified.get("canonical_post_id") or latest_verified.get("post_id")
        )
        truth_state = "VERIFIED_PUBLISHED"
        proof = "durable publication-log record contains a canonical post_id and verified API-response proof; publisher result file is missing or empty"
        proof_source = "publication_log_durable_proof"
        latest_id = durable_id
    elif latest and str(latest.get("status") or "") == "PUBLISH_BLOCKED_DUPLICATE":
        truth_state = "SKIPPED_DUPLICATE"
        proof = "duplicate-safety rule intentionally stopped publication; no new Binance Square post was created by this cycle"
        proof_source = "publication_log_control_flow"
    elif latest and str(latest.get("status") or "") == "PUBLISH_SKIPPED_WTE_INELIGIBLE":
        truth_state = "SKIPPED_WTE_INELIGIBLE"
        proof = "Write-to-Earn eligibility gate intentionally stopped publication; no new Binance Square post was submitted"
        proof_source = "publication_log_control_flow"
    elif latest and str(latest.get("status") or "") == "PUBLISHED_SUBMITTED_504":
        truth_state = "SUBMITTED_UNKNOWN"
        proof = "Binance content/add returned HTTP 504 after submission; no canonical post id was returned, so the post is not treated as verified"
        proof_source = "publication_log_unknown_submission"
    elif latest and str(latest.get("status") or ""):
        truth_state = "ATTEMPTED_NOT_VERIFIED"
        proof = "publication attempt exists but canonical Binance post-id proof is missing or inconsistent"
        proof_source = "publication_log_attempt"
    else:
        truth_state = "NO_ATTEMPT"
        proof = "no durable publication record is available"
        proof_source = "none"

    result = {
        "version": "20.5-durable-log-recovery",
        "checked_at": now,
        "truth_state": truth_state,
        "proof": proof,
        "proof_source": proof_source,
        "latest_publication": latest,
        "publisher_result": result_file,
        "publisher_result_present": bool(result_file),
        "publisher_result_post_id": result_id or None,
        "canonical_post_id": (canonical_post_id(
            matched_log.get("canonical_post_id") or matched_log.get("post_id")
        ) if matched_log else latest_id) or None,
        "post_id_match": bool(
            result_id
            and matched_log
            and canonical_post_id(
                matched_log.get("canonical_post_id") or matched_log.get("post_id")
            ) == result_id
        ),
        "durable_log_verified": bool(latest_verified),
        "publication_count_observed": len(rows),
        "rules": {
            "post_id_required_for_verified_state": True,
            "publisher_and_log_ids_should_match_when_result_exists": True,
            "durable_verified_log_can_recover_empty_result_file": True,
            "submission_unknown_is_not_verified": True,
            "intentional_skips_are_not_failures": True,
            "revenue_inferred": False,
            "gate_bypass": False,
            "credential_changes": False,
        },
    }

    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    (LIVE / "creator_20_0_publication_truth.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    report = {
        "version": result["version"],
        "generated_at": now,
        "truth_state": truth_state,
        "publication_count_observed": len(rows),
        "latest_post_id": result["canonical_post_id"],
        "latest_link": (
            (matched_log or latest or {}).get("link")
            if (matched_log or latest)
            else None
        ),
        "proof": proof,
        "proof_source": proof_source,
        "post_id_match": result["post_id_match"],
        "durable_log_verified": result["durable_log_verified"],
    }
    (INTEL / "creator_20_0_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    memory_path = ANALYTICS / "creator_20_0_memory.json"
    memory = read_json(memory_path, {"checks": []}) or {"checks": []}
    checks = memory.get("checks") if isinstance(memory.get("checks"), list) else []
    checks.append(
        {
            "checked_at": now,
            "truth_state": truth_state,
            "post_id": result["canonical_post_id"],
            "post_id_match": result["post_id_match"],
            "proof_source": proof_source,
        }
    )
    memory["checks"] = checks[-200:]
    memory["latest_truth_state"] = truth_state
    memory["latest_canonical_post_id"] = result["canonical_post_id"]
    memory_path.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
