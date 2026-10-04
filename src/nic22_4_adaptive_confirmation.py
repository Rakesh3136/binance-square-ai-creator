"""NIC 22.4 — Adaptive confirmation and opportunity recovery.

A near-miss is never promoted by lowering the safety threshold. This controller
only authorizes one bounded fresh-evidence recheck per creator cycle.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

CONFIRMATION=Path("data/live/nic22_3_early_confirmation.json")
WATCH=Path("data/live/nic22_3_developing_watch.json")
OUT=Path("data/live/nic22_4_adaptive_confirmation.json")
MIN_SCORE=50.0
MAX_SCORE=59.99
MAX_RECHECKS=1

def load(p, default):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception:
        return default

def main():
    now=datetime.now(timezone.utc).isoformat()
    c=load(CONFIRMATION,{})
    w=load(WATCH,{})
    score=float(c.get("confirmation_score",0) or 0)
    near=bool(c.get("near_miss")) and MIN_SCORE<=score<=MAX_SCORE
    symbol=str(w.get("symbol") or (c.get("selected_opportunity") or {}).get("symbol") or "").upper()
    if near and symbol:
        payload={
            "version":"22.4-adaptive-confirmation",
            "generated_at":now,
            "status":"RECHECK_AUTHORIZED",
            "symbol":symbol,
            "previous_score":round(score,2),
            "gap_to_confirmation":round(60.0-score,2),
            "recheck_count":1,
            "max_rechecks":MAX_RECHECKS,
            "policy":{
                "fresh_evidence_required":True,
                "threshold_unchanged":True,
                "no_threshold_lowering":True,
                "no_trade_from_watch_only":True,
                "promotion_requires_independent_confirmation":True
            },
            "action":"refresh_market_evidence_then_rerun_nic22_2_and_nic22_3_once"
        }
    else:
        payload={
            "version":"22.4-adaptive-confirmation",
            "generated_at":now,
            "status":"NO_RECHECK",
            "symbol":symbol or None,
            "previous_score":round(score,2),
            "recheck_count":0,
            "max_rechecks":MAX_RECHECKS,
            "policy":{"threshold_unchanged":True,"no_threshold_lowering":True}
        }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(payload,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
