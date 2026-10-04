"""NIC 23.1 append-only Trade Experience Ledger.

Predictions are immutable once recorded. Outcomes are appended as separate events.
A later outcome can update the learning view, but can never rewrite the original
prediction snapshot. This prevents hindsight contamination.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
PREDICTION = LIVE / "nic_prediction_engine.json"
LEDGER = LIVE / "nic_trade_experience_ledger.jsonl"
OUTCOMES = LIVE / "nic_trade_outcome_events.jsonl"
STATE = LIVE / "nic_trade_experience_state.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def ids_from(path: Path) -> set[str]:
    ids = set()
    if not path.exists():
        return ids
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("prediction_id"):
                ids.add(str(row["prediction_id"]))
        except json.JSONDecodeError:
            continue
    return ids


def make_prediction_id(row: dict) -> str:
    return sha256({
        "symbol": row.get("symbol"),
        "side": row.get("side"),
        "created_at": row.get("created_at") or row.get("generated_at"),
        "trigger": (row.get("recommended_setup") or {}).get("trigger"),
        "invalidation": (row.get("recommended_setup") or {}).get("invalidation"),
        "tp1": (row.get("recommended_setup") or {}).get("tp1"),
        "tp2": (row.get("recommended_setup") or {}).get("tp2"),
    })[:24]


def record_predictions() -> int:
    doc = read_json(PREDICTION, {})
    candidates = doc.get("candidates") if isinstance(doc.get("candidates"), list) else []
    existing = ids_from(LEDGER)
    added = 0
    for row in candidates:
        if not isinstance(row, dict) or str(row.get("status", "")).upper() != "PASS":
            continue
        pid = make_prediction_id(row)
        if pid in existing:
            continue
        setup = row.get("recommended_setup") if isinstance(row.get("recommended_setup"), dict) else {}
        snapshot = {
            "symbol": str(row.get("symbol") or "").upper(),
            "side": str(row.get("side") or "").upper(),
            "created_at": row.get("created_at") or row.get("generated_at") or now(),
            "quality_score": row.get("quality_score"),
            "calibrated_confidence": row.get("calibrated_confidence"),
            "setup_type": row.get("setup_type") or row.get("setup_family") or "unknown",
            "market_regime": row.get("market_regime") or row.get("regime") or "unknown",
            "timeframe": row.get("timeframe") or "unknown",
            "recommended_setup": {
                "trigger": setup.get("trigger"),
                "invalidation": setup.get("invalidation"),
                "tp1": setup.get("tp1"),
                "tp2": setup.get("tp2"),
            },
            "walk_forward": row.get("walk_forward") if isinstance(row.get("walk_forward"), dict) else {},
            "latest_completed_candle": row.get("latest_completed_candle") if isinstance(row.get("latest_completed_candle"), dict) else {},
        }
        record = {
            "record_type": "PREDICTION_SNAPSHOT",
            "schema_version": "1.0",
            "prediction_id": pid,
            "recorded_at": now(),
            "prediction": snapshot,
            "prediction_hash": sha256(snapshot),
            "immutable": True,
        }
        append_jsonl(LEDGER, record)
        existing.add(pid)
        added += 1
    return added


def main() -> int:
    added = record_predictions()
    state = {
        "schema_version": "1.0",
        "updated_at": now(),
        "new_prediction_snapshots": added,
        "prediction_ledger": str(LEDGER.relative_to(ROOT)),
        "outcome_event_log": str(OUTCOMES.relative_to(ROOT)),
        "policy": [
            "Prediction snapshots are append-only and immutable.",
            "Outcomes are appended as separate events.",
            "Learning may consume outcomes but may not mutate historical prediction snapshots.",
            "Corrections require a new correction event referencing the original prediction_id.",
            "Future training uses only information timestamped before the prediction event for prediction features.",
        ],
    }
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
