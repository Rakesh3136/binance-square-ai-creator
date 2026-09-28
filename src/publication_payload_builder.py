"""Build the exact final publication payload immediately before submission.

This eliminates stale publication_payload.json reuse across creator cycles.
Only data already present in the final draft/context/frozen contract is copied.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
OUT = LIVE / "publication_payload.json"
CONTEXT = LIVE / "publication_context.json"
FROZEN = LIVE / "authoritative_opportunity.json"
MONETIZATION_OS = LIVE / "nic_monetization_contract.json"


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def clean_symbol(v: object) -> str:
    s = re.sub(r"USDT$", "", str(v or "").upper().replace("$", "").strip())
    return s if re.fullmatch(r"[A-Z0-9]{1,15}", s) else ""


def main() -> int:
    raw = os.environ.get("DRAFT_PATH", "").strip()
    if not raw:
        print("ERROR: DRAFT_PATH is required", file=sys.stderr)
        return 2
    path = Path(raw)
    if not path.exists():
        print(f"ERROR: draft does not exist: {path}", file=sys.stderr)
        return 2

    report = load(path)
    draft = report.get("draft") if isinstance(report.get("draft"), dict) else {}
    context = load(CONTEXT)
    frozen = load(FROZEN)
    monetization_os = load(MONETIZATION_OS)

    text = str(draft.get("post") or draft.get("text") or "").strip()
    symbol = clean_symbol(
        context.get("symbol")
        or report.get("selected_editorial_lane", {}).get("symbol")
        or draft.get("symbol")
        or frozen.get("symbol")
    )
    category = str(
        context.get("category")
        or report.get("selected_editorial_lane", {}).get("category")
        or draft.get("content_category")
        or frozen.get("category")
        or ""
    ).lower().strip()

    if not text:
        print("ERROR: final publication text is empty", file=sys.stderr)
        return 2
    if not symbol:
        print("ERROR: final publication symbol is missing", file=sys.stderr)
        return 2

    payload = {
        "status": "READY_FOR_PUBLISH",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_draft": str(path),
        "title": str(draft.get("title") or context.get("title") or "").strip(),
        "text": text,
        "symbol": symbol,
        "category": category,
        "direction": str(
            context.get("direction")
            or (context.get("prediction") or {}).get("direction")
            or frozen.get("direction")
            or (frozen.get("prediction") or {}).get("direction")
            or ""
        ).upper(),
        "experiment_id": str(
            monetization_os.get("experiment_id")
            or context.get("experiment_id")
            or frozen.get("experiment_id")
            or draft.get("experiment_id")
            or ""
        ),
        "campaign_day": monetization_os.get("campaign_day", context.get("campaign_day")),
        "content_lane": str(monetization_os.get("content_lane") or context.get("content_lane") or category),
        "content_format": str(monetization_os.get("content_format") or context.get("content_format") or draft.get("experiment_format") or ""),
        "hook_type": str(monetization_os.get("hook_type") or context.get("hook_type") or ""),
        "visual_type": str(monetization_os.get("visual_type") or context.get("visual_type") or ""),
        "reader_payoff_type": str(monetization_os.get("reader_payoff_type") or context.get("reader_payoff_type") or ""),
        "experiment_variable": str(monetization_os.get("experiment_variable") or context.get("experiment_variable") or ""),
        "experiment_treatment": str(monetization_os.get("experiment_treatment") or context.get("experiment_treatment") or ""),
        "cycle_id": str(monetization_os.get("cycle_id") or context.get("cycle_id") or ""),
        "cashtag": str(monetization_os.get("cashtag") or ("$" + symbol if symbol else ""))
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "source_draft": payload["source_draft"],
        "symbol": symbol,
        "category": category,
        "characters": len(text),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
