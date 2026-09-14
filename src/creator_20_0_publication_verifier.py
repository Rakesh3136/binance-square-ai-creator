"""Durable Binance Square publication truth verifier.

Creator 9.2: VERIFIED_PUBLISHED requires a concrete canonical post id from
the publisher's Binance OpenAPI response and a matching durable log record.
Unknown/504 submissions remain explicitly unverified.
"""
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


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def canonical_post_id(value) -> str:
    raw = str(value or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw = raw.split("/square/post/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    return raw if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw) else ""


def read_publications() -> list[dict]:
    path = ANALYTICS / "publication_log.jsonl"
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    rows = read_publications()
    latest = rows[-1] if rows else None
    result_file = read_json(RESULT, {}) or {}
    result_id = canonical_post_id(result_file.get("canonical_post_id") or result_file.get("post_id"))
    log_id = canonical_post_id(latest.get("canonical_post_id") or latest.get("post_id")) if latest else ""
    status = str(latest.get("status") or "") if latest else ""
    verified_status = status in {"PUBLISHED_VERIFIED_BY_API_RESPONSE", "VERIFIED_PUBLISHED", "PUBLISHED_AUTONOMOUSLY"}
    ids_match = bool(result_id and log_id and result_id == log_id)
    has_verified_id = bool(log_id and verified_status and latest.get("publication_id_verified") is not False)

    if has_verified_id and ids_match:
        truth_state = "VERIFIED_PUBLISHED"
        proof = "publisher result and durable publication log agree on the canonical Binance Square post_id"
    elif latest and status == "PUBLISHED_SUBMITTED_504":
        truth_state = "SUBMITTED_UNKNOWN"
        proof = "Binance submission returned a post-submit 504 condition without a post_id; publication is intentionally not treated as verified"
    elif latest and status:
        truth_state = "ATTEMPTED_NOT_VERIFIED"
        proof = "publication attempt exists but canonical Binance post-id proof is missing or inconsistent"
    else:
        truth_state = "NO_ATTEMPT"
        proof = "no durable publication record is available"

    result = {
        "version": "20.2-creator-9.2-live-proof",
        "checked_at": now,
        "truth_state": truth_state,
        "proof": proof,
        "latest_publication": latest,
        "publisher_result": result_file,
        "canonical_post_id": log_id or result_id or None,
        "post_id_match": ids_match,
        "publication_count_observed": len(rows),
        "rules": {
            "post_id_required_for_verified_state": True,
            "publisher_and_log_ids_must_match": True,
            "submission_unknown_is_not_verified": True,
            "revenue_inferred": False,
            "gate_bypass": False,
            "credential_changes": False,
        },
    }
    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    (LIVE / "creator_20_0_publication_truth.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    report = {
        "version": "20.2-creator-9.2-live-proof",
        "generated_at": now,
        "truth_state": truth_state,
        "publication_count_observed": len(rows),
        "latest_post_id": log_id or None,
        "latest_link": latest.get("link") if latest else None,
        "proof": proof,
        "post_id_match": ids_match,
    }
    (INTEL / "creator_20_0_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    memory_path = ANALYTICS / "creator_20_0_memory.json"
    memory = read_json(memory_path, {"checks": []}) or {"checks": []}
    checks = memory.get("checks") if isinstance(memory.get("checks"), list) else []
    checks.append({
        "checked_at": now,
        "truth_state": truth_state,
        "post_id": log_id or result_id or None,
        "post_id_match": ids_match,
    })
    memory["checks"] = checks[-200:]
    memory["latest_truth_state"] = truth_state
    memory["latest_canonical_post_id"] = log_id or result_id or None
    memory_path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # The pre-publication verifier is allowed to see NO_ATTEMPT. Once a
    # publisher result exists, however, a non-verified state is fail-closed.
    if RESULT.exists() and result_file and truth_state not in {"VERIFIED_PUBLISHED", "NO_ATTEMPT"}:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
