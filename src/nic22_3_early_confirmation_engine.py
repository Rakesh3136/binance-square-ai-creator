"""NIC 22.3.1 — Early Signal Confirmation with near-miss telemetry."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

EARLY=Path("data/live/nic22_2_early_selection.json")
PRE=Path("data/live/editorial_preflight.json")
OUT=Path("data/live/nic22_3_early_confirmation.json")
SELECTION=Path("data/live/nic22_3_confirmation_selection.json")
NEAR_MISS=Path("data/live/nic22_3_near_miss.json")
MIN_SCORE=60.0
MIN_SIGNALS=4
MAX_PRICE_MOVE=5.0
NEAR_MISS_MIN_SCORE=50.0

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
    score=0.0; signals=[]; breakdown={}
    move=abs(num(c.get("price_change_percent"))); vol=num(c.get("volume_acceleration")); med=num(c.get("volume_vs_24h_median")); rs=num(c.get("relative_strength_24h")); oi=num(c.get("oi_change_3h_pct")); dist=num(c.get("breakout_distance_pct"),99); discovery=num(c.get("discovery_score"))
    def add(name,points):
        nonlocal score
        score += points; breakdown[name]=points; signals.append(name)
    if vol>=1.5: add("volume_acceleration",15)
    elif vol>=1.25: add("volume_acceleration",10)
    if med>=1.5: add("volume_vs_24h_median",12)
    elif med>=1.2: add("volume_vs_24h_median",7)
    if rs>=2: add("relative_strength",12)
    elif rs>=0.5: add("relative_strength",7)
    if oi>=2: add("open_interest_context",12)
    elif oi>=1: add("open_interest_context",7)
    if 0<dist<=3: add("breakout_proximity",12)
    elif 3<dist<=5: add("breakout_proximity",7)
    if discovery>=60: add("universe_discovery_score",10)
    elif discovery>=50: add("universe_discovery_score",5)
    if move<=2.5 and vol>=1.5: add("low_extension_with_participation",8)
    return round(min(100.0,score),2),signals,breakdown

def main():
    early=load(EARLY,{})
    candidate=early.get("selected_opportunity") if isinstance(early.get("selected_opportunity"),dict) else None
    generated=datetime.now(timezone.utc).isoformat()
    if not candidate:
        payload={"version":"22.3.1-early-signal-confirmation","generated_at":generated,"status":"BLOCKED","reason":"no_nic22_2_selected_candidate","selected_opportunity":None}
        OUT.write_text(json.dumps(payload,indent=2),encoding="utf-8"); SELECTION.write_text(json.dumps(payload,indent=2),encoding="utf-8"); return 1
    move=abs(num(candidate.get("price_change_percent"))); score,signals,breakdown=confirm_score(candidate); state=str(candidate.get("flow_state") or "").upper(); unique_count=len(set(signals))
    eligible=state in {"EARLY","DEVELOPING"} and move<=MAX_PRICE_MOVE and score>=MIN_SCORE and unique_count>=MIN_SIGNALS
    selected=None
    if eligible:
        selected=dict(candidate); selected.update({"confirmation_score":score,"confirmation_signals":signals,"confirmation_score_breakdown":breakdown,"confirmation_status":"CONFIRMED_EARLY_SETUP","requires_invalidation":True})
        selected["confirmation_policy"]={"present_conditions_only":True,"no_future_price_guarantee":True,"invalidation_required":True,"independent_signal_count":unique_count}
    near_miss=(not selected and state in {"EARLY","DEVELOPING"} and move<=MAX_PRICE_MOVE and score>=NEAR_MISS_MIN_SCORE and unique_count>=MIN_SIGNALS)
    payload={"version":"22.3.1-early-signal-confirmation","generated_at":generated,"status":"CONFIRMED" if selected else "BLOCKED","reason":"multiple_independent_early_conditions_confirmed" if selected else "insufficient_independent_confirmation","selected_opportunity":selected,"observed_signal_count":unique_count,"observed_signals":signals,"confirmation_score":score,"score_breakdown":breakdown,"near_miss":near_miss,"rules":{"min_score":MIN_SCORE,"min_independent_signals":MIN_SIGNALS,"max_abs_price_move_pct":MAX_PRICE_MOVE,"near_miss_min_score":NEAR_MISS_MIN_SCORE,"no_prediction_guarantee":True,"invalidation_required":True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8"); SELECTION.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    if near_miss:
        NEAR_MISS.write_text(json.dumps({"version":"22.3.1-near-miss","generated_at":generated,"status":"WATCH_ONLY","symbol":candidate.get("symbol"),"flow_state":state,"confirmation_score":score,"observed_signals":signals,"score_breakdown":breakdown,"gap_to_confirmation":round(MIN_SCORE-score,2),"publication_allowed":False,"recheck_on_next_cycle":True},indent=2,ensure_ascii=False),encoding="utf-8")
    elif NEAR_MISS.exists(): NEAR_MISS.unlink()
    if selected:
        pre=load(PRE,{})
        symbol=str(selected.get("symbol") or selected.get("topic") or "").upper(); pool=pre.get("candidate_pool") if isinstance(pre.get("candidate_pool"),list) else []
        pre["candidate_pool"]=[dict(x,**selected) for x in pool if str(x.get("symbol") or x.get("topic") or "").upper()==symbol] or [selected]
        pre["selected_opportunity"]=selected; pre["nic22_3_confirmation"]=payload; pre["run_ai"]=True; PRE.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(payload,indent=2,ensure_ascii=False)); return 0 if selected else 1

if __name__=="__main__": raise SystemExit(main())
