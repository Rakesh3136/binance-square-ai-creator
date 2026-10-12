"""Fail-closed eligibility for the editorial-only publication lane."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_editorial_lane_gate.json"

def fresh(data, max_age_minutes=45):
    raw = str(data.get("generated_at") or data.get("timestamp") or "").strip()
    if not raw:
        return False
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 60
        return 0 <= age <= max_age_minutes
    except Exception:
        return False

def evaluate(eligibility, routing, challenge):
    reasons = []
    if eligibility.get("eligible") is not True:
        reasons.append("current-cycle publication eligibility is not true")
    if str(eligibility.get("publication_mode") or "").upper() != "EDITORIAL":
        reasons.append("publication mode is not EDITORIAL")
    if eligibility.get("trade_authorized") is not False:
        reasons.append("editorial lane must explicitly deny trade authorization")
    if routing.get("publish") is not True:
        reasons.append("Signal-First did not authorize this cycle for publication")
    decision = str(challenge.get("decision") or "").upper()
    if decision not in {"EDITORIAL_SIGNAL", "EDITORIAL", "RESEARCH", "NO_TRADE"}:
        reasons.append("current decision is not an editorial/research decision")
    if not fresh(eligibility):
        reasons.append("publication eligibility is missing or stale")
    if not fresh(routing):
        reasons.append("Signal-First routing decision is missing or stale")
    if not fresh(challenge):
        reasons.append("counterfactual challenge decision is missing or stale")
    ok = not reasons
    return {
        "schema": "NIC-EDITORIAL-LANE-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "EDITORIAL_ELIGIBLE" if ok else "BLOCKED",
        "publish": ok,
        "publication_mode": "EDITORIAL" if ok else "BLOCKED",
        "trade_authorized": False,
        "reasons": reasons,
        "policy": "Editorial permission only. Trade calls, levels, and live orders remain unauthorized."
    }

def main():
    def load(name):
        try:
            value = json.loads((LIVE / name).read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    result = evaluate(
        load("nic22_5_publication_eligibility.json"),
        load("signal_first_routing.json"),
        load("nic23_5_counterfactual_challenge.json"),
    )
    LIVE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["publish"] else 24

if __name__ == "__main__":
    raise SystemExit(main())
