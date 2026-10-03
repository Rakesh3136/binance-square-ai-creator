"""NIC 22.2 — Early Opportunity Detection.

Filters the full-universe flow scan for EARLY/DEVELOPING setups before the
diversity selector can choose a late mover. This is an evidence gate, not a
prediction engine: it identifies developing conditions and requires confirmation
and invalidation in downstream editorial stages.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

FLOW=Path("data/live/full_universe_flow.json")
PREFLIGHT=Path("data/live/editorial_preflight.json")
OUT=Path("data/live/nic22_2_early_opportunities.json")
SELECTION=Path("data/live/nic22_2_early_selection.json")

MIN_SCORE=45.0
MAX_PRICE_MOVE=5.0
MIN_VOLUME_ACCEL=1.25
MAX_CANDIDATES=40

def load(p, default):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, type(default)) else default
    except Exception:
        return default

def num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def early_score(x):
    score=num(x.get("discovery_score"))
    move=abs(num(x.get("price_change_percent")))
    vol=num(x.get("volume_acceleration"))
    median=num(x.get("volume_vs_24h_median"))
    dist=num(x.get("breakout_distance_pct"), 99)
    rs=num(x.get("relative_strength_24h"))
    oi=num(x.get("oi_change_3h_pct"))
    # Penalize extension aggressively; reward independent participation/structure
    # evidence. No term here implies that a future pump is certain.
    s=score
    if move > 10: s -= 45
    elif move > 7: s -= 30
    elif move > 5: s -= 18
    elif move > 3: s -= 6
    s += min(12, max(0, (vol-1)*5))
    s += min(8, max(0, (median-1)*4))
    s += min(7, max(0, rs))
    s += min(6, max(0, oi))
    if 1.0 <= dist <= 5.0: s += 7
    return round(max(0, min(100, s)), 2)

def main():
    flow=load(FLOW,{})
    raw=flow.get("early_movers") if isinstance(flow.get("early_movers"),list) else []
    candidates=[]
    for x in raw:
        if not isinstance(x,dict): continue
        state=str(x.get("flow_state") or "").upper()
        move=abs(num(x.get("price_change_percent")))
        if state not in {"EARLY","DEVELOPING"}: continue
        if move > MAX_PRICE_MOVE: continue
        if num(x.get("volume_acceleration")) < MIN_VOLUME_ACCEL: continue
        score=early_score(x)
        if score < MIN_SCORE: continue
        candidates.append({
            "type":"early_flow",
            "category":"early_setup",
            "topic":str(x.get("symbol_usdt") or x.get("symbol") or "").upper(),
            "symbol":str(x.get("symbol") or "").upper(),
            "raw_score":score,
            "adjusted_score":score,
            "reason":"early/developing participation before significant price extension",
            "flow_state":state,
            "price_change_percent":x.get("price_change_percent"),
            "volume_acceleration":x.get("volume_acceleration"),
            "volume_vs_24h_median":x.get("volume_vs_24h_median"),
            "relative_strength_24h":x.get("relative_strength_24h"),
            "oi_change_3h_pct":x.get("oi_change_3h_pct"),
            "funding_rate":x.get("funding_rate"),
            "breakout_distance_pct":x.get("breakout_distance_pct"),
            "discovery_score":x.get("discovery_score"),
            "evidence":x.get("evidence") or [],
            "confirmation_required":True,
            "editorial_instruction":"Treat this as an early setup candidate, not a pump prediction. Explain observed evidence, confirmation trigger, invalidation and uncertainty."
        })
    candidates.sort(key=lambda x:(x["adjusted_score"], -abs(num(x["price_change_percent"]))), reverse=True)
    candidates=candidates[:MAX_CANDIDATES]

    # The full-universe scanner is authoritative for early discovery. Do not
    # intersect it with the older editorial preflight pool: an early asset may
    # legitimately be absent from top-gainer/volume/news lists. Enrich when a
    # matching preflight candidate exists, but never discard a valid early setup.
    pre=load(PREFLIGHT,{})
    original=list(pre.get("candidate_pool") or [])
    merged=[]
    for e in candidates:
        match=next((c for c in original if str(c.get("topic") or c.get("symbol") or "").upper()==e["symbol"]), None)
        merged.append({**(match or {}), **e})
    pre["nic22_2"]={
        "version":"22.2-early-opportunity-detection",
        "status":"SELECTED" if merged else "BLOCKED",
        "candidate_count":len(merged),
        "original_preflight_candidate_count":len(original),
        "policy":{"max_abs_price_move_pct":MAX_PRICE_MOVE,"min_volume_acceleration":MIN_VOLUME_ACCEL,"no_late_mover_fallback":True,"no_prediction_guarantee":True,"confirmation_required":True}
    }
    pre["run_ai"]=bool(merged)
    pre["reason"]="nic22_2_early_setup_selected" if merged else "no_early_setup_candidate"
    PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")

    payload={"version":"22.2-early-opportunity-detection","generated_at":datetime.now(timezone.utc).isoformat(),"status":"SELECTED" if candidates else "BLOCKED","selected_opportunity":candidates[0] if candidates else None,"candidates":candidates,"rules":{"max_abs_price_move_pct":MAX_PRICE_MOVE,"min_volume_acceleration":MIN_VOLUME_ACCEL,"min_score":MIN_SCORE,"no_late_mover_fallback":True,"confirmation_required":True,"no_prediction_guarantee":True}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    SELECTION.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":payload["status"],"early_candidates":len(candidates),"selected":payload["selected_opportunity"]},indent=2))
    return 0 if candidates else 1

if __name__=="__main__":
    raise SystemExit(main())
