"""NIC 23.4 — Contextual Signal Quality Authority.

This is a conservative classification layer, not an execution engine. It combines
validated prediction evidence, contextual experience, and calibration health.
It never changes entry/stop/target levels and cannot override deterministic gates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRED=ROOT/"data/live/nic_prediction_engine.json"
VALID=ROOT/"data/live/nic_prediction_contract_validation.json"
EXP=ROOT/"data/live/nic_adaptive_experience.json"
CAL=ROOT/"data/live/nic_probability_calibration.json"
OUT=ROOT/"data/live/nic_contextual_signal_authority.json"
AUTH_THRESHOLD=80

def load(path):
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def num(x,default=None):
    try:return float(x)
    except (TypeError,ValueError):return default

def main():
    pred=load(PRED); valid=load(VALID); exp=load(EXP); cal=load(CAL)
    candidates=pred.get("candidates") if isinstance(pred.get("candidates"),list) else []
    profiles=exp.get("profiles") if isinstance(exp.get("profiles"),list) else []
    profile_map={(str(x.get("setup_type","")).upper(),str(x.get("side","")).upper(),
                  str(x.get("timeframe","")).upper(),str(x.get("market_regime","")).upper()):x for x in profiles}
    validation_errors=valid.get("errors") if isinstance(valid.get("errors"),list) else []
    calibrated_state=str(cal.get("state") or "INSUFFICIENT_DATA").upper()
    rows=[]
    for row in candidates:
        if not isinstance(row,dict) or str(row.get("status","")).upper()!="PASS":continue
        symbol=str(row.get("symbol") or "").upper()
        side=str(row.get("side") or "").upper()
        setup=row.get("recommended_setup") if isinstance(row.get("recommended_setup"),dict) else {}
        state=str(setup.get("state") or "").upper()
        wf=row.get("walk_forward") if isinstance(row.get("walk_forward"),dict) else {}
        samples=int(num(wf.get("terminal_samples"),0) or 0)
        wr=num(wf.get("win_rate"))
        key=(str(row.get("setup_type") or row.get("setup_family") or "UNKNOWN").upper(),side,
             str(row.get("timeframe") or "UNKNOWN").upper(),str(row.get("market_regime") or row.get("regime") or "UNKNOWN").upper())
        profile=profile_map.get(key)
        hard=[]
        if not symbol or side not in {"LONG","SHORT"}:hard.append("invalid_prediction_identity")
        if samples<25:hard.append("insufficient_walk_forward_samples")
        if wr is None or wr<0.55:hard.append("historical_edge_below_threshold")
        if num(row.get("calibrated_confidence")) is None or num(row.get("calibrated_confidence"))>85:hard.append("confidence_policy_breach")
        if state!="AWAITING_TRIGGER":hard.append("setup_not_awaiting_trigger")
        if any(isinstance(e,dict) and str(e.get("symbol","")).upper()==symbol and e.get("failures") for e in validation_errors):
            hard.append("prediction_contract_not_validated")
        score=100
        reasons=[]
        if profile is None or int(profile.get("samples",0) or 0)<25:
            score-=15; reasons.append("contextual_experience_not_established")
        if calibrated_state=="POORLY_CALIBRATED":
            score-=15; reasons.append("probability_calibration_poor")
        elif calibrated_state=="NEEDS_RECALIBRATION":
            score-=7; reasons.append("probability_calibration_needs_review")
        elif calibrated_state=="INSUFFICIENT_DATA":
            score-=3; reasons.append("calibration_sample_small")
        if profile and num(profile.get("empirical_win_rate")) is not None and num(profile.get("empirical_win_rate"))<0.55:
            score-=15; reasons.append("contextual_win_rate_below_threshold")
        authority="NO_TRADE" if hard else ("AUTHORIZED" if score>=AUTH_THRESHOLD else "WATCH_ONLY")
        rows.append({"symbol":symbol,"side":side,"authority":authority,"authority_score":score,
                     "hard_failures":hard,"advisories":reasons,"context_key":list(key),
                     "context_samples":int(profile.get("samples",0) or 0) if profile else 0,
                     "calibration_state":calibrated_state})
    result={"schema":"NIC-CONTEXTUAL-AUTHORITY-1.0","generated_at":datetime.now(timezone.utc).isoformat(),
      "candidates":rows,"policy":["Authority is classification only; it does not execute trades.",
      "It cannot modify frozen entry, invalidation, TP1 or TP2.","Insufficient evidence produces WATCH_ONLY or NO_TRADE.",
      "Historical prediction records remain immutable.","No authority state is a guarantee or probability of profit.",
      "AUTHORIZED is still subject to downstream publication and safety gates."]}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2))
if __name__=="__main__":main()
