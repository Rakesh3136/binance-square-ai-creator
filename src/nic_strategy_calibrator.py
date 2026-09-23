"""Conservative bridge from verified NIC outcomes to strategy weights.

This is continual strategy calibration, not foundation-model training. It only
produces advisory weights; deterministic signal/risk/publication gates remain
authoritative.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/live/nic_outcome_ledger.jsonl"
OUT = ROOT / "data/live/nic_strategy_weights.json"
MIN_SAMPLES = 10


def rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict) and x.get("verified"): out.append(x)
        except Exception: pass
    return out


def main():
    data=rows()
    n=len(data)
    wins=sum(x.get("outcome") in {"TP1","TP2"} for x in data)
    losses=sum(x.get("outcome") in {"SL","INVALIDATED"} for x in data)
    ambiguous=sum(x.get("outcome") in {"AMBIGUOUS","EXPIRED"} for x in data)
    if n < MIN_SAMPLES:
        state="FROZEN_INSUFFICIENT_DATA"
        weight=1.0
    else:
        # Bounded advisory weight. It never changes price/risk contracts.
        rate=wins/n
        weight=max(0.75,min(1.25,0.75+0.5*rate))
        state="CALIBRATED"
    result={
      "schema":"NIC-WEIGHTS-1.0",
      "updated_at":datetime.now(timezone.utc).isoformat(),
      "verified_samples":n,"wins":wins,"losses":losses,"ambiguous":ambiguous,
      "state":state,
      "default_strategy_weight":weight,
      "weights_are_advisory":True,
      "frozen_contract_immutable":True,
      "risk_gates_immutable":True,
      "publication_gates_immutable":True,
      "promotion_threshold":MIN_SAMPLES,
      "note":"Weights are bounded and may inform ensemble calibration only; they cannot create or publish a signal."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__ == "__main__": main()
