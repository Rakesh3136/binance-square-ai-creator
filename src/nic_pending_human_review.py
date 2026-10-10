"""Preserve the exact NIC draft for a human-review pause/resume handoff.

This module never publishes. It packages an immutable review target and verifies
that an approval still refers to the same draft before downstream orchestration.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
PENDING = LIVE / "nic_pending_human_review.json"
BRIEF = LIVE / "nic_human_creator_brief.json"
INPUT = LIVE / "nic_human_creator_input.json"
MAX_EVIDENCE_AGE_SECONDS = 15 * 60


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def canonical_text(report: dict) -> str:
    draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
    for key in ("post", "text", "body", "content", "caption"):
        value = draft.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("text", "post"):
        value = report.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prepare(draft_path: Path, pending_path: Path = PENDING) -> dict:
    report = read_json(draft_path)
    text = canonical_text(report)
    if not text:
        raise ValueError("cannot preserve a draft without publishable text")
    brief = read_json(BRIEF)
    expected = sha256_text(text)
    if brief and brief.get("draft_sha256") != expected:
        raise ValueError("review brief hash does not match the draft being preserved")
    draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
    symbol = str(draft.get("symbol") or draft.get("ticker") or brief.get("symbol") or "").strip().upper()
    package = {
        "schema": "NIC-PENDING-HUMAN-REVIEW-1.0",
        "status": "PENDING_HUMAN_REVIEW",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "draft_path": str(draft_path.resolve()),
        "draft_text_sha256": expected,
        "draft_file_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
        "symbol": symbol or None,
        "draft_text": text,
        "human_review_brief": str(BRIEF.relative_to(ROOT)) if BRIEF.exists() else None,
        "policy": {
            "immutable_draft_required": True,
            "approval_must_match_exact_draft": True,
            "publication_authorized": False,
            "must_revalidate_market_and_chart_before_resume": True,
        },
    }
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package


def verify_approval(package: dict, human_input: dict, draft_path: Path) -> list[str]:
    failures = []
    if package.get("schema") != "NIC-PENDING-HUMAN-REVIEW-1.0":
        failures.append("pending_package_schema_invalid")
    if package.get("status") != "PENDING_HUMAN_REVIEW":
        failures.append("pending_package_not_waiting_for_review")
    try:
        report = read_json(draft_path)
        text = canonical_text(report)
        file_hash = hashlib.sha256(draft_path.read_bytes()).hexdigest()
    except OSError:
        text, file_hash = "", ""
    if not text or sha256_text(text) != package.get("draft_text_sha256"):
        failures.append("pending_draft_text_changed_or_missing")
    if file_hash != package.get("draft_file_sha256"):
        failures.append("pending_draft_file_changed_or_missing")
    if human_input.get("draft_sha256") != package.get("draft_text_sha256"):
        failures.append("approval_hash_does_not_match_pending_draft")
    if human_input.get("approved_for_publication") is not True:
        failures.append("explicit_approval_missing")
    for field, minimum in (("human_thesis", 30), ("original_insight", 30), ("evidence_reviewed", 20)):
        value = human_input.get(field)
        if not isinstance(value, str) or len(value.strip()) < minimum:
            failures.append(f"{field}_missing_or_too_short")
    if human_input.get("author_attestation") != "I reviewed the evidence and authored the editorial contribution":
        failures.append("author_attestation_missing")
    if not package.get("symbol"):
        failures.append("pending_symbol_missing")
    return failures


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify"))
    parser.add_argument("--draft-path", required=True)
    parser.add_argument("--pending-path", default=str(PENDING))
    parser.add_argument("--input-path", default=str(INPUT))
    args = parser.parse_args()
    path = Path(args.draft_path)
    if not path.is_absolute():
        path = ROOT / path
    pending_path = Path(args.pending_path)
    if not pending_path.is_absolute():
        pending_path = ROOT / pending_path
    input_path = Path(args.input_path)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    if args.command == "prepare":
        result = prepare(path, pending_path)
        print(json.dumps({"status": result["status"], "draft_text_sha256": result["draft_text_sha256"], "symbol": result["symbol"], "publication_authorized": False}, indent=2))
        return 0
    package = read_json(pending_path)
    human = read_json(input_path)
    failures = verify_approval(package, human, path)
    print(json.dumps({"status": "APPROVAL_VALIDATION_PASS" if not failures else "BLOCKED", "failures": failures, "publication_authorized": False}, indent=2))
    # Verification is not publication; orchestration must still rerun live gates.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
