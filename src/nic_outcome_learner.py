"""NIC outcome ledger + safe continual-learning bridge.

This is not foundation-model training. It converts verified prediction and
publication outcomes into auditable strategy observations. No learned value
can bypass deterministic publication gates.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
ANALYTICS = ROOT / "analytics"
LEDGER = LIVE / "nic_outcome_ledger.jsonl"
REPORT = LIVE / "nic_learning_state.json"
MEMORY = ANALYTICS / "strategy_memory.json"


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def rows(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict):
                out.append(x)
        except Exception:
            pass
    return out


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    outcome = read_json(LIVE / "prediction_outcomes.json", {})
    publication = read_json(LIVE / "publication_result.json", {})
    contract = read_json(LIVE / "prediction_contract.json", {})

    status = str(outcome.get("status") or outcome.get("outcome") or "UNVERIFIED").upper()
    verified = status in {"TP1", "TP2", "SL", "INVALIDATED", "AMBIGUOUS", "EXPIRED"} or bool(outcome.get("verified"))
    record = {
        "recorded_at": now(),
        "symbol": outcome.get("symbol") or contract.get("symbol"),
        "prediction_id": outcome.get("prediction_id") or contract.get("prediction_id"),
        "outcome": status,
        "verified": verified,
        "entry": outcome.get("entry") or contract.get("entry"),
        "tp1": outcome.get("tp1") or contract.get("tp1"),
        "tp2": outcome.get("tp2") or contract.get("tp2"),
        "sl": outcome.get("sl") or contract.get("sl"),
        "publication_status": publication.get("status") or publication.get("publication_status"),
        "publication_proof": bool(publication.get("post_id") or publication.get("publication_proof")),
    }

    existing = rows(LEDGER)
    key = (record.get("prediction_id"), record.get("symbol"), record.get("outcome"))
    if not any((x.get("prediction_id"), x.get("symbol"), x.get("outcome")) == key and key[0] for x in existing):
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        existing.append(record)

    verified_rows = [x for x in existing if x.get("verified")]
    wins = sum(x.get("outcome") in {"TP1", "TP2"} for x in verified_rows)
    losses = sum(x.get("outcome") in {"SL", "INVALIDATED"} for x in verified_rows)
    ambiguous = sum(x.get("outcome") in {"AMBIGUOUS", "EXPIRED"} for x in verified_rows)
    samples = len(verified_rows)

    # Conservative calibration signal: never promote strategy changes from a
    # single sample and never modify deterministic risk/price contracts here.
    calibration = "INSUFFICIENT_DATA" if samples < 10 else ("POSITIVE" if wins > losses else "REVIEW")
    state = {
        "schema": "NIC-LEARN-1.0",
        "updated_at": now(),
        "verified_outcomes": samples,
        "wins": wins,
        "losses": losses,
        "ambiguous": ambiguous,
        "calibration_state": calibration,
        "training_mode": "OUTCOME_LEARNING_NOT_FOUNDATION_MODEL_TRAINING",
        "deterministic_contract_immutable": True,
        "publication_gates_immutable": True,
        "learning_can_change": ["strategy_weights", "confidence_calibration", "content_experiment_priority"],
        "learning_cannot_change": ["frozen_price_contract", "risk_gates", "publication_safety_gates"],
        "next_requirement": "Collect >=10 independently verified outcomes before promoting a strategy-weight change.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
