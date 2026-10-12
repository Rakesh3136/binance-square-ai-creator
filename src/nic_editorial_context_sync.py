"""Synchronize editorial generation to the current frozen opportunity, fail-closed."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_editorial_context_sync.json"

def parse_time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def fresh(data, now, max_age_minutes=45):
    dt = parse_time(data.get("generated_at") or data.get("timestamp"))
    return dt is not None and 0 <= (now - dt).total_seconds() <= max_age_minutes * 60

def evaluate(routing, frozen, eligibility, preflight, now=None):
    now = now or datetime.now(timezone.utc)
    reasons = []
    decision = str(routing.get("decision") or "").upper()
    mode = str(eligibility.get("publication_mode") or "").upper()
    routed = routing.get("selected") if isinstance(routing.get("selected"), dict) else {}
    route_symbol = str(routed.get("symbol") or "").upper().replace("USDT", "").replace("$", "").strip()
    frozen_symbol = str(frozen.get("symbol") or "").upper().replace("USDT", "").replace("$", "").strip()
    if routing.get("publish") is not True:
        reasons.append("Signal-First did not authorize this cycle")
    if decision not in {"EDITORIAL_SIGNAL", "EDITORIAL", "RESEARCH", "NO_TRADE"}:
        reasons.append("current Signal-First decision is not editorial")
    if eligibility.get("eligible") is not True or mode != "EDITORIAL":
        reasons.append("current publication eligibility is not editorial-eligible")
    if eligibility.get("trade_authorized") is not False:
        reasons.append("editorial handoff requires explicit trade_authorized=false")
    if not route_symbol or not frozen_symbol or route_symbol != frozen_symbol:
        reasons.append("frozen asset does not match current Signal-First selected asset")
    if not fresh(routing, now):
        reasons.append("Signal-First decision is missing or stale")
    if not fresh(eligibility, now):
        reasons.append("publication eligibility is missing or stale")
    route_time = parse_time(routing.get("generated_at") or routing.get("timestamp"))
    frozen_time = parse_time(frozen.get("frozen_at") or frozen.get("generated_at") or frozen.get("timestamp"))
    if route_time is None or frozen_time is None or frozen_time < route_time:
        reasons.append("frozen opportunity is missing a valid post-routing timestamp")
    if not isinstance(preflight, dict):
        reasons.append("editorial preflight is malformed")
    ok = not reasons
    updated = dict(preflight) if isinstance(preflight, dict) else {}
    if ok:
        # Frozen opportunity is authoritative; do not carry stale symbol/thesis fields forward.
        updated["selected_opportunity"] = dict(frozen)
        updated.pop("creator_brain_decision", None)
        updated["editorial_authoritative_handoff"] = {
            "status": "SYNCED",
            "symbol": frozen_symbol,
            "decision_id": str(routing.get("decision_id") or ""),
            "frozen_at": frozen_time.isoformat(),
            "synced_at": now.isoformat(),
            "trade_authorized": False,
        }
    return {
        "schema": "NIC-EDITORIAL-CONTEXT-SYNC-1.0",
        "generated_at": now.isoformat(),
        "status": "SYNCED" if ok else "BLOCKED",
        "publish": ok,
        "symbol": frozen_symbol if ok else "",
        "reasons": reasons,
        "preflight": updated if ok else None,
        "trade_authorized": False,
    }

def load(name):
    try:
        value = json.loads((LIVE / name).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def main():
    result = evaluate(
        load("signal_first_routing.json"),
        load("authoritative_opportunity.json"),
        load("nic22_5_publication_eligibility.json"),
        load("editorial_preflight.json"),
    )
    LIVE.mkdir(parents=True, exist_ok=True)
    if result["publish"]:
        (LIVE / "editorial_preflight.json").write_text(
            json.dumps(result["preflight"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    report = {key: value for key, value in result.items() if key != "preflight"}
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if result["publish"] else 24

if __name__ == "__main__":
    raise SystemExit(main())
