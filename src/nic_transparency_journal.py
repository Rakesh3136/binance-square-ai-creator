"""Build a transparent, user-readable NIC learning/decision journal.

This intentionally records decision summaries, evidence, uncertainty, outcomes and
lessons. It does NOT expose hidden chain-of-thought or private internal reasoning.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
INTEL = ROOT / "data" / "intelligence"
OUT = LIVE / "nic_transparency_journal.json"
REPORT = INTEL / "nic_transparency_report.json"

SOURCES = {
    "prediction": LIVE / "nic_prediction_engine.json",
    "accuracy_gate": LIVE / "nic_prediction_accuracy_gate.json",
    "learning": LIVE / "learning_engine.json",
    "self_training": LIVE / "creator_self_training.json",
    "content_master": LIVE / "content_master_training.json",
    "opportunity_genome": LIVE / "nic_opportunity_genome.json",
    "experiment_governor": LIVE / "nic_experiment_governor.json",
    "publication": LIVE / "publisher_result.json",
    "publication_payload": LIVE / "publication_payload.json",
    "dashboard": LIVE / "nic_dashboard.json",
}

def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def first(d: dict, *keys):
    for key in keys:
        value = d.get(key)
        if value not in (None, "", [], {}):
            return value
    return None

def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    data = {name: load(path) for name, path in SOURCES.items()}

    prediction = data["prediction"]
    accuracy = data["accuracy_gate"]
    learning = data["learning"]
    training = data["self_training"]
    master = data["content_master"]
    genome = data["opportunity_genome"]
    experiments = data["experiment_governor"]
    publication = data["publication"]
    payload = data["publication_payload"]

    symbol = first(prediction, "symbol", "asset") or first(payload, "symbol")
    direction = first(prediction, "direction", "bias") or first(payload, "direction")
    evidence = first(prediction, "evidence_score", "score")
    confidence = first(prediction, "confidence", "confidence_score")
    gate = first(accuracy, "status", "decision", "gate")
    experiment_id = first(experiments, "experiment_id") or first(payload, "experiment_id")

    lessons = []
    for obj, label in ((learning, "learning engine"), (training, "self-training"),
                       (master, "content master"), (genome, "opportunity genome")):
        for key in ("lesson", "latest_lesson", "learning", "insight", "summary"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                lessons.append({"source": label, "text": value.strip()})
                break
        if len(lessons) >= 4:
            break

    journal = {
        "schema_version": "1.0",
        "timestamp": now,
        "run_id": os.getenv("GITHUB_RUN_ID", ""),
        "run_number": os.getenv("GITHUB_RUN_NUMBER", ""),
        "purpose": "Transparent NIC decision and learning summary",
        "transparency_policy": {
            "exposes": ["decision_summary", "evidence", "uncertainty", "outcome", "lessons", "next_experiment"],
            "does_not_expose": ["hidden_chain_of_thought", "private_internal_reasoning"]
        },
        "decision_summary": {
            "symbol": symbol,
            "direction": direction,
            "evidence_score": evidence,
            "confidence": confidence,
            "accuracy_gate": gate,
            "experiment_id": experiment_id,
        },
        "what_i_observed": [
            x for x in [
                f"Primary asset: {symbol}" if symbol else None,
                f"Modelled direction/bias: {direction}" if direction else None,
                f"Evidence score: {evidence}" if evidence is not None else None,
                f"Accuracy gate: {gate}" if gate else None,
            ] if x
        ],
        "lessons": lessons,
        "outcome": {
            "publication_status": first(publication, "status"),
            "post_id": first(publication, "post_id", "canonical_post_id"),
            "publication_proof": first(publication, "publication_proof"),
        },
        "next_experiment": {
            "experiment_id": experiment_id,
            "governor": experiments.get("decision") or experiments.get("selected_strategy") or experiments.get("strategy"),
        },
        "shareable_note": (
            "NIC field note — "
            + (f"I focused on {symbol}. " if symbol else "")
            + (f"The current evidence score was {evidence}. " if evidence is not None else "")
            + (f"The prediction direction was {direction}. " if direction else "")
            + "I will compare this decision with the verified outcome and use that result to calibrate the next cycle."
        ),
    }

    LIVE.mkdir(parents=True, exist_ok=True)
    INTEL.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(journal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(journal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "TRANSPARENCY_JOURNAL_READY",
        "symbol": symbol,
        "direction": direction,
        "lessons": len(lessons),
        "publication_status": journal["outcome"]["publication_status"],
        "shareable_note": journal["shareable_note"],
    }, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
