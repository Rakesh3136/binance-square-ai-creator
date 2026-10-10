"""NIC Human Creator Collaboration Gate.

Builds a review brief from the current draft and requires real human editorial
contribution before publication. This does not attempt to disguise AI authorship.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/live/nic_human_creator_input.json"
BRIEF = ROOT / "data/live/nic_human_creator_brief.json"
OUT = ROOT / "data/live/nic_human_creator_gate.json"
REPORT_DIR = ROOT / "data/reports"


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def draft_text(report: dict) -> str:
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


def resolve_draft() -> Path | None:
    raw = os.getenv("DRAFT_PATH", "").strip()
    if raw:
        path = Path(raw)
        return path if path.is_file() else None
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def validate_human_input(post: str, human_input: dict) -> list[str]:
    failures = []
    required = {
        "human_thesis": 30,
        "original_insight": 30,
        "evidence_reviewed": 20,
    }
    if human_input.get("approved_for_publication") is not True:
        failures.append("explicit_human_approval_missing")
    for field, min_len in required.items():
        value = human_input.get(field)
        if not isinstance(value, str) or len(value.strip()) < min_len:
            failures.append(f"{field}_missing_or_too_short")
    if not post:
        failures.append("draft_text_missing")
    expected_hash = hashlib.sha256(post.encode("utf-8")).hexdigest() if post else ""
    if human_input.get("draft_sha256") != expected_hash:
        failures.append("human_review_does_not_match_current_draft")
    if human_input.get("author_attestation") != "I reviewed the evidence and authored the editorial contribution":
        failures.append("author_attestation_missing")
    return failures


def build_brief(post: str, report: dict, draft_path: Path) -> dict:
    draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
    symbol = str(draft.get("symbol") or draft.get("ticker") or "").strip()
    if not symbol:
        match = re.search(r"\$([A-Z][A-Z0-9]{1,14})", post.upper())
        symbol = match.group(1) if match else ""
    return {
        "version": "NIC-HUMAN-CREATOR-BRIEF-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "draft_path": str(draft_path),
        "draft_sha256": hashlib.sha256(post.encode("utf-8")).hexdigest() if post else "",
        "symbol": symbol,
        "draft_text": post,
        "review_prompts": [
            "What is your own thesis, in your own words, beyond the draft's summary?",
            "What specific insight did you find that a generic market recap would miss?",
            "Which evidence did you personally inspect, and what could disprove your thesis?",
            "Does the chart match the asset, timeframe, levels and argument?",
            "Do you approve this exact draft for publication?",
        ],
        "input_contract": {
            "file": "data/live/nic_human_creator_input.json",
            "required_fields": ["draft_sha256", "human_thesis", "original_insight", "evidence_reviewed", "approved_for_publication", "author_attestation"],
            "minimum_characters": {"human_thesis": 30, "original_insight": 30, "evidence_reviewed": 20},
        },
        "policy": "No fabricated personal experience, no authorship disguise, no publication without current-draft human review.",
    }


def evaluate(post: str, human_input: dict, draft_path: str = "") -> dict:
    failures = validate_human_input(post, human_input)
    return {
        "version": "NIC-HUMAN-CREATOR-GATE-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "BLOCKED",
        "publish": not failures,
        "failures": failures,
        "draft_sha256": hashlib.sha256(post.encode("utf-8")).hexdigest() if post else "",
        "draft_path": draft_path,
        "policy": {
            "requires_genuine_human_editorial_contribution": True,
            "requires_approval_of_exact_draft": True,
            "does_not_attempt_to_disguise_ai_authorship": True,
            "no_gate_bypass": True,
        },
    }


def main() -> int:
    path = resolve_draft()
    report = load_json(path) if path else {}
    post = draft_text(report)
    brief = build_brief(post, report, path) if path else {
        "version": "NIC-HUMAN-CREATOR-BRIEF-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "draft_text": "",
        "draft_sha256": "",
        "review_prompts": [],
        "failures": ["current_draft_missing"],
    }
    human_input = load_json(INPUT)
    result = evaluate(post, human_input, str(path or ""))
    BRIEF.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "publish": result["publish"], "failures": result["failures"], "brief": str(BRIEF), "input": str(INPUT)}, indent=2))
    # A quality block is a valid no-publication decision, not a broken CI run.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
