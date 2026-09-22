"""Independent decision ensemble for the frozen opportunity.

This is deliberately provider-neutral: it combines independent deterministic
signals already produced by the creator instead of adding another opaque model.
It is a review/calibration layer, never a market-data authority.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "decision_ensemble.json"


def load(name: str) -> dict:
    p = LIVE / name
    try:
        x = json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def number(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def main() -> int:
    frozen = load("authoritative_opportunity.json")
    signal = load("signal_first_routing.json")
    regime = load("market_regime_intelligence.json")
    adversarial = load("adversarial_decision.json")
    counterfactual = load("counterfactual_analysis.json")
    research = load("research_intelligence.json")

    direction = str(frozen.get("direction") or "").upper()
    contract = all(frozen.get(k) is not None for k in ("entry_trigger", "tp1", "tp2", "sl"))
    signal_ok = signal.get("publish") is True and bool(signal.get("selected"))
    frozen_ok = bool(frozen.get("binance_verified")) and direction in {"LONG", "SHORT"} and contract

    votes = []
    votes.append({"agent":"signal_first","decision":"PASS" if signal_ok else "BLOCK","reason":"authoritative signal router"})
    votes.append({"agent":"frozen_contract","decision":"PASS" if frozen_ok else "BLOCK","reason":"live symbol + direction + complete setup contract"})

    # Optional specialist outputs are consumed when present. Missing specialists
    # never become fake PASS votes.
    for name, data in (("adversarial", adversarial), ("counterfactual", counterfactual), ("research", research)):
        if not data:
            continue
        blocked = bool(data.get("blocked") is True or str(data.get("decision") or data.get("status") or "").upper() in {"BLOCK", "BLOCKED", "FAIL", "FAILED"})
        explicit_pass = bool(data.get("approved") is True or data.get("publish") is True or str(data.get("decision") or "").upper() in {"PASS", "APPROVE", "APPROVED"})
        votes.append({"agent":name,"decision":"BLOCK" if blocked else ("PASS" if explicit_pass else "REVIEW"),"reason":str(data.get("reason") or data.get("message") or "specialist output")[:500]})

    passes = sum(v["decision"] == "PASS" for v in votes)
    blocks = sum(v["decision"] == "BLOCK" for v in votes)
    reviews = sum(v["decision"] == "REVIEW" for v in votes)
    total = len(votes)

    # Hard deterministic failures always block. Otherwise disagreement is REVIEW,
    # not an automatic publication approval.
    if not frozen_ok or not signal_ok:
        decision = "BLOCK"
    elif blocks:
        decision = "REVIEW"
    elif reviews:
        decision = "REVIEW"
    else:
        decision = "PASS"

    result = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": frozen.get("symbol"),
        "direction": direction,
        "decision": decision,
        "publish_authorized": decision == "PASS",
        "vote_count": total,
        "passes": passes,
        "blocks": blocks,
        "reviews": reviews,
        "disagreement": bool(blocks or reviews),
        "votes": votes,
        "policy": "Independent reviewers may require review, but cannot override deterministic market/evidence failures.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if decision != "BLOCK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
