"""NIC 22.3 — Early Signal Confirmation Engine.

Confirms that an early candidate has multiple independent pieces of observed
evidence before publication. Confirmation is about the present setup, not a
guarantee of future price movement.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

EARLY=Path("data/live/nic22_2_early_selection.json")
PRE=Path("data/live/editorial_preflight.json")
OUT=Path("data/live/nic22_3_early_confirmation.json")
SELECTION=Path("data/live/nic22_3_confirmation_selection.json")

MIN_SCORE=60.0
MIN_SIGNALS=4
MAX_PRICE_MOVE=5.0

def load(p, default):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception:
        return default

def num(v, default=0.0):
    try: return float(v)
    except Exception: return default

def confirm_score(c):
    score=0.0
    signals=[]
    move=abs(num(c.get("price_change_percent")))
    vol=num(c.get("volume_acceleration"))
    med=num(c.get("volume_vs_24h_median"))
    rs=num(c.get("relative_strength_24h"))
    oi=num(c.get("oi_change_3h_pct"))
    dist=num(c.get("breakout_distance_pct"),99)
    discovery=num(c.get("discovery_score"))

    # Independent observed-condition buckets. No bucket claims future direction.
    if vol >= 1.5:
        score += 15; signals.append("volume_acceleration")
    elif vol >= 1.25:
        score += 10; signals.append("volume_acceleration")
    if med >= 1.5:
        score += 12; signals.append("volume_vs_24h_median")
    elif med >= 1.2:
        score += 7; signals.append("volume_vs_24h_median")
    if rs >= 2:
        score += 12; signals.append("relative_strength")
    elif rs >= 0.5:
        score += 7; signals.append("relative_strength")
    if oi >= 2:
        score += 12; signals.append("open_interest_context")
    elif oi >= 1:
        score += 7; signals.append("open_interest_context")
    if 0 < dist <= 3:
        score += 12; signals.append("breakout_proximity")
    elif 3 < dist <= 5:
        score += 7; signals.append("breakout_proximity")
    if discovery >= 60:
        score += 10; signals.append("universe_discovery_score")
    elif discovery >= 50:
        score += 5; signals.append("universe_discovery_score")
    # Compression proxy: small move plus participation is preferable to extension.
    if move <= 2.5 and vol >= 1.5:
        score += 8; signals.append("low_extension_with_participation")
    return round(min(100.0,score),2),signals

def main():
    early=load(EARLY,{})
    candidate=early.get("selected_opportunity") if isinstance(early.get("selected_opportunity"),dict) else None
    if not candidate:
        payload={"version":"22.3-early-signal-confirmation","generated_at":datetime.now(timezone.utc).isoformat(),"status":"BLOCKED","reason":"no_nic22_2_selected_candidate","selected_opportunity":None}
        OUT.write_text(json.dumps(payload,indent=2),encoding="utf-8"); SELECTION.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        return 1

    move=abs(num(candidate.get("price_change_percent")))
    score,signals=confirm_score(candidate)
    state=str(candidate.get("flow_state") or "").upper()
    eligible=(state in {"EARLY","DEVELOPING"} and move <= MAX_PRICE_MOVE and score >= MIN_SCORE and len(set(signals)) >= MIN_SIGNALS)

    selected=None
    if eligible:
        selected=dict(candidate)
        selected["confirmation_score"]=score
        selected["confirmation_signals"]=signals
        selected["confirmation_status"]="CONFIRMED_EARLY_SETUP"
        selected["confirmation_policy"]={
            "present_conditions_only":True,
            "no_future_price_guarantee":True,
            "invalidation_required":True,
            "independent_signal_count":len(set(signals)),
        }
        # Force a concrete invalidation concept downstream even when the writer
        # later chooses exact chart levels from verified market data.
        selected["requires_invalidation"]=True

    payload={
        "version":"22.3-early-signal-confirmation",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"CONFIRMED" if selected else "BLOCKED",
        "reason":"multiple_independent_early_conditions_confirmed" if selected else "insufficient_independent_confirmation",
        "selected_opportunity":selected,
        "observed_signal_count":len(set(signals)),
        "observed_signals":signals,
        "confirmation_score":score,
        "rules":{"min_score":MIN_SCORE,"min_independent_signals":MIN_SIGNALS,"max_abs_price_move_pct":MAX_PRICE_MOVE,"no_prediction_guarantee":True,"invalidation_required":True}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    SELECTION.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")

    if selected:
        pre=load(PRE,{})
        # Confirmation becomes authoritative for the existing candidate; do not
        # reopen the universe or select a replacement after this point.
        pre["selected_opportunity"]=selected
        pre["nic22_3_confirmation"]=payload
        pre["run_ai"]=True
        PRE.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(payload,indent=2,ensure_ascii=False))
    return 0 if selected else 1

if __name__=="__main__":
    raise SystemExit(main())
