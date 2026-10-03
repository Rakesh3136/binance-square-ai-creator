"""NIC 22.3.2 — Persist developing early setups without publishing them."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
CONFIRMATION=Path("data/live/nic22_3_early_confirmation.json")
EARLY=Path("data/live/nic22_2_early_selection.json")
WATCH=Path("data/live/nic22_3_developing_watch.json")
HISTORY=Path("data/live/nic22_3_developing_history.json")
MIN_SCORE=45.0
MAX_SCORE=59.99
MAX_PRICE_MOVE=5.0
MAX_CYCLES=3

def load(path, default):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,type(default)) else default
    except Exception:
        return default

def main():
    now=datetime.now(timezone.utc).isoformat()
    confirmation=load(CONFIRMATION,{})
    early=load(EARLY,{})
    score=float(confirmation.get("confirmation_score",0.0) or 0.0)
    candidate=confirmation.get("selected_opportunity")
    if not isinstance(candidate,dict):
        candidate=early.get("selected_opportunity") if isinstance(early.get("selected_opportunity"),dict) else None
    signals=confirmation.get("observed_signals",[])
    breakdown=confirmation.get("score_breakdown",{})
    symbol=str((candidate or {}).get("symbol","")).upper()
    move=abs(float((candidate or {}).get("price_change_percent",0.0) or 0.0))
    watch=load(WATCH,{})
    history=load(HISTORY,[])
    if not isinstance(history,list): history=[]
    eligible=(not bool(confirmation.get("selected_opportunity")) and bool(symbol) and MIN_SCORE<=score<=MAX_SCORE and len(set(signals))>=4 and move<=MAX_PRICE_MOVE)
    if eligible:
        previous=int(watch.get("cycles_observed",0) or 0) if watch.get("symbol")==symbol and watch.get("status")=="WATCH_ONLY" else 0
        cycles=previous+1
        status="WATCH_ONLY" if cycles<=MAX_CYCLES else "EXPIRED"
        watch={"version":"22.3.2-developing-setup-monitor","generated_at":now,"status":status,"symbol":symbol,"confirmation_score":round(score,2),"gap_to_confirmation":round(60.0-score,2),"observed_signals":signals,"score_breakdown":breakdown,"price_move_pct":round(move,4),"cycles_observed":cycles,"max_cycles":MAX_CYCLES,"publication_allowed":False,"recheck_on_next_cycle":status=="WATCH_ONLY","expiry_reason":"watch_cycle_limit_reached" if status=="EXPIRED" else None}
        history=(history+[watch.copy()])[-50:]
    else:
        watch={"version":"22.3.2-developing-setup-monitor","generated_at":now,"status":"NONE","publication_allowed":False,"recheck_on_next_cycle":False}
    WATCH.parent.mkdir(parents=True,exist_ok=True)
    WATCH.write_text(json.dumps(watch,indent=2,ensure_ascii=False),encoding="utf-8")
    HISTORY.write_text(json.dumps(history,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(watch,indent=2,ensure_ascii=False))
    return 0
if __name__=="__main__": raise SystemExit(main())
