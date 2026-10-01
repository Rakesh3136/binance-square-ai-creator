"""Validate the final visual contains authoritative trade markings when a setup lane requires them."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
META=ROOT/"data/live/visual_metadata.json"
PREF=ROOT/"data/live/editorial_preflight.json"
def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else {}
    except Exception:return {}
def main():
    meta=load(META); pre=load(PREF); selected=pre.get("selected_opportunity") or {}
    category=str(selected.get("category") or "").lower()
    setup=selected.get("trade_setup") or {}
    pred=selected.get("prediction") or {}
    technical=category in {"technical_setup","capital_flow_long","capital_flow_short","high_volatility","top_gainers","top_losers","flow","follow_up","creator_signal_outcome"}
    if not technical:
        print({"status":"SKIP","reason":"non-setup lane"}); return 0
    markings=meta.get("prediction_markings") or {}
    required=("entry_trigger","tp1","tp2","sl")
    missing=[k for k in required if markings.get(k) is None]
    if not bool(meta.get("overlays")) or missing:
        raise SystemExit(f"FINAL VISUAL CONTRACT FAILED: overlays={meta.get('overlays')} missing={missing}")
    print({"status":"PASS","overlay_type":meta.get("overlay_type"),"prediction_markings":markings})
    return 0
if __name__=="__main__": raise SystemExit(main())
