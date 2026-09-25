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
    contract = read_json(LIVE / "prediction_contract.json", {})
    publication = read_json(LIVE / "publication_result.json", {})

    # Learn only from the corrected trigger-first evaluator. This deliberately
    # ignores legacy outcome labels produced by the previous accounting logic.
    evaluated = []
    for row in rows(PREDICTION_OUTCOMES):
        version = str(row.get("evaluator_version") or "")
        outcome = str(row.get("outcome") or "").upper()
        if version.startswith("25.") and outcome in {"WIN", "INVALIDATED", "AMBIGUOUS"}:
            evaluated.append(row)

    # One terminal label per call_id: latest terminal record wins.
    terminal_by_call = {}
    for row in evaluated:
        cid = str(row.get("call_id") or "")
        if cid:
            terminal_by_call[cid] = row
    evaluated = list(terminal_by_call.values())

    wins = sum(str(x.get("outcome")).upper() == "WIN" for x in evaluated)
    losses = sum(str(x.get("outcome")).upper() == "INVALIDATED" for x in evaluated)
    ambiguous = sum(str(x.get("outcome")).upper() == "AMBIGUOUS" for x in evaluated)
    samples = len(evaluated)
    win_rate = wins / max(wins + losses, 1)

    record = {
        "recorded_at": now(),
        "symbol": contract.get("symbol") or None,
        "prediction_id": contract.get("prediction_id") or None,
        "outcome": "BATCH_SUMMARY",
        "verified": True,
        "publication_status": publication.get("status"),
        "publication_proof": bool(publication.get("post_id") or publication.get("publication_proof")),
        "evaluator_version": "25.0-trigger-first-state-machine",
        "terminal_samples": samples,
        "wins": wins,
        "losses": losses,
        "ambiguous": ambiguous,
        "win_rate": round(win_rate, 4) if wins + losses else None,
    }

    existing = rows(LEDGER)
    batch_key = f"25.0|{samples}|{wins}|{losses}|{ambiguous}"
    if not any(str(x.get("batch_key") or "") == batch_key for x in existing):
        record["batch_key"] = batch_key
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        existing.append(record)

    state = {
        "schema": "NIC-LEARN-2.0",
        "updated_at": now(),
        "verified_terminal_outcomes": samples,
        "wins": wins,
        "losses": losses,
        "ambiguous": ambiguous,
        "win_rate_excluding_ambiguous": round(win_rate, 4) if wins + losses else None,
        "calibration_state": "INSUFFICIENT_DATA" if samples < 10 else ("POSITIVE" if wins > losses else "REVIEW"),
        "training_mode": "POST_FIX_OUTCOME_LEARNING",
        "legacy_outcomes_excluded": True,
        "deterministic_contract_immutable": True,
        "publication_gates_immutable": True,
        "learning_can_change": [
            "strategy_weights",
            "confidence_calibration",
            "prediction_quality_threshold",
            "content_experiment_priority",
        ],
        "learning_cannot_change": [
            "frozen_price_contract",
            "risk_gates",
            "publication_safety_gates",
        ],
        "next_requirement": "Collect >=10 post-fix terminal outcomes before promoting prediction-strategy changes.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
