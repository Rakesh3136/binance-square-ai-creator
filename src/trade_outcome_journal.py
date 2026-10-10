"""Evidence-first journal for evaluating published NIC trade ideas.

Outcomes and prediction quality are intentionally separate. A profitable move
is not proof that the original thesis was well supported, and an unverified
claim is never counted as a measured win.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_OUTCOMES = {"verified_win", "verified_loss", "breakeven", "unresolved"}
VALID_QUALITY = {"supported", "mixed", "unsupported", "not_assessed"}
VALID_LEARNING = {"incorporated", "pending", "excluded"}
DEFAULT_PATH = Path("analytics/trade_outcome_journal.jsonl")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate a single journal event without inventing missing trade facts."""
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")

    trade_id = str(record.get("trade_id") or "").strip()
    symbol = str(record.get("symbol") or "").strip().upper()
    direction = str(record.get("direction") or "").strip().lower()
    if not trade_id:
        raise ValueError("trade_id is required")
    if not symbol:
        raise ValueError("symbol is required")
    if direction not in {"long", "short", "long_term_bullish", "long_term_bearish"}:
        raise ValueError("direction must explicitly identify the thesis direction")

    outcome = str(record.get("outcome") or "unresolved").strip().lower()
    quality = str(record.get("prediction_quality") or "not_assessed").strip().lower()
    learning = str(record.get("learning_status") or "pending").strip().lower()
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    if quality not in VALID_QUALITY:
        raise ValueError(f"prediction_quality must be one of {sorted(VALID_QUALITY)}")
    if learning not in VALID_LEARNING:
        raise ValueError(f"learning_status must be one of {sorted(VALID_LEARNING)}")

    evidence = record.get("outcome_evidence") or []
    if not isinstance(evidence, list) or any(not str(x).strip() for x in evidence):
        raise ValueError("outcome_evidence must be a list of non-empty evidence references")

    # A win/loss/breakeven is only verified when traceable evidence is supplied.
    if outcome != "unresolved" and not evidence:
        raise ValueError("a resolved outcome requires outcome_evidence; use unresolved otherwise")
    if learning == "incorporated" and (outcome == "unresolved" or quality == "not_assessed"):
        raise ValueError("learning cannot be marked incorporated before outcome and quality are assessed")

    normalized = {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "published_at": record.get("published_at"),
        "entry_price": record.get("entry_price"),
        "stop_loss": record.get("stop_loss"),
        "target_price": record.get("target_price"),
        "time_horizon": record.get("time_horizon"),
        "invalidation_condition": record.get("invalidation_condition"),
        "outcome": outcome,
        "outcome_evidence": [str(x).strip() for x in evidence],
        "prediction_quality": quality,
        "quality_evidence": [str(x).strip() for x in (record.get("quality_evidence") or [])],
        "learning_status": learning,
        "realized_pnl": record.get("realized_pnl"),
        "notes": str(record.get("notes") or ""),
        "recorded_at": str(record.get("recorded_at") or _utc_now()),
    }
    return normalized


def append_record(record: dict[str, Any], path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    """Append one validated event to JSONL. Existing events are never overwritten."""
    normalized = validate_record(record)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n")
    return normalized


def read_latest(path: str | Path = DEFAULT_PATH) -> dict[str, dict[str, Any]]:
    """Return the latest event for each trade_id while preserving the source log."""
    source = Path(path)
    latest: dict[str, dict[str, Any]] = {}
    if not source.exists():
        return latest
    with source.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                validated = validate_record(item)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid journal event on line {line_no}: {exc}") from exc
            latest[validated["trade_id"]] = validated
    return latest


def summary(path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    """Report verified outcomes separately from prediction quality and learning."""
    records = list(read_latest(path).values())
    outcomes = {key: sum(r["outcome"] == key for r in records)
                for key in sorted(VALID_OUTCOMES)}
    quality = {key: sum(r["prediction_quality"] == key for r in records)
               for key in sorted(VALID_QUALITY)}
    learning = {key: sum(r["learning_status"] == key for r in records)
                for key in sorted(VALID_LEARNING)}
    return {
        "trade_count": len(records),
        "outcomes": outcomes,
        "prediction_quality": quality,
        "learning_status": learning,
        "verified_outcome_count": sum(outcomes[k] for k in ("verified_win", "verified_loss", "breakeven")),
        "unresolved_count": outcomes["unresolved"],
        "warning": "Outcome counts are not a profitability claim; evaluate risk, timing, and evidence separately.",
    }
