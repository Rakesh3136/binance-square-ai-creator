"""NIC Forecast evidence adapter: resolved predictive edge plus regime stability."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/"data/live/nic_forecast_laboratory.json"
MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
CALIB=ROOT/"data/intelligence/nic_forecast_calibration.json"
GOV=ROOT/"data/intelligence/nic_forecast_governance.json"
def load(p):
    try:
        v=json.loads(p.read_text())
        return v if isinstance(v,dict) else {}
    except Exception: return {}
def evidence(symbol, side):
    s=str(symbol or "").upper().replace("USDT","").strip()
    fs={"LONG":"BULLISH","SHORT":"BEARISH"}.get(str(side or "").upper(),"")
    results=load(LAB).get("results") or []
    current=next((r for r in results if isinstance(r,dict) and str(r.get("symbol") or "").upper()==s and r.get("status")=="READY"),{})
    regime=str(current.get("regime") or "")
    matrix=load(MATRIX).get("matrix") or {}
    cells=[r for r in matrix.values() if isinstance(r,dict) and str(r.get("side")).upper()==fs and str(r.get("regime"))==regime and r.get("trusted")]
    lifts=[float(r.get("lift") or 0) for r in cells]
    cal=load(CALIB).get("cells") or {}
    gov=load(GOV).get("cells") or {}
    probs=[r for r in cal.values() if isinstance(r,dict) and str(r.get("side")).upper()==fs and str(r.get("regime"))==regime and r.get("trusted")]
    probability=(sum(float(r.get("calibrated_probability") or .5) for r in probs)/len(probs)) if probs else .5
    probability_trusted=bool(probs)
    governance=[]
    for key,row in gov.items():
        if isinstance(row,dict) and str(row.get("side")).upper()==fs and str(row.get("regime"))==regime:
            governance.append(row)
    governance_state="RECOVERY"
    trust_multiplier=0.5
    if governance:
        best=max(governance,key=lambda x:int(x.get("horizon_hours") or 0))
        governance_state=str(best.get("state") or "RECOVERY")
        trust_multiplier=float(best.get("trust_multiplier") or 0.0)
    try:
        from nic_regime_transition import evaluate
        transition=evaluate(s)
    except Exception:
        transition={"transition_state":"UNKNOWN","regime_stability":0.0,"edge_decay_penalty":0.0,"usable":False}
    raw_score=min(12.0,4.0*len(cells)+max(0.0,max(lifts or [0]))*100)
    decay=float(transition.get("edge_decay_penalty") or 0)
    return {"symbol":s,"side":fs,"regime":regime,"trusted_cells":len(cells),
            "max_lift":round(max(lifts or [0]),4),
            "evidence_score":round(raw_score*(1.0-decay)*trust_multiplier,2),
            "raw_evidence_score":round(raw_score,2),
            "calibrated_probability":round(probability,4),
            "probability_trusted":probability_trusted,
            "regime_transition_state":transition.get("transition_state"),
            "regime_stability":transition.get("regime_stability",0.0),
            "edge_decay_penalty":decay,
            "governance_state":governance_state,"governance_trust_multiplier":round(trust_multiplier,2),
            "advisory_only":True,"publish_gate_unchanged":True}
if __name__=="__main__":
    print(json.dumps({"schema":"NIC-FORECAST-EVIDENCE-2.0","status":"READY","policy":"Resolved predictive evidence is regime-aware and decay-adjusted; it cannot override timing, diversity, cooldown, or publication gates."},indent=2))
