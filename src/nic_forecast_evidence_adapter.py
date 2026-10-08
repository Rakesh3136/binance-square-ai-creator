"""NIC Forecast evidence adapter: resolved predictive edge plus regime and signal-family governance."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/"data/live/nic_forecast_laboratory.json"
MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
CALIB=ROOT/"data/intelligence/nic_forecast_calibration.json"
GOV=ROOT/"data/intelligence/nic_forecast_governance.json"
FAMILY_GOV=ROOT/"data/intelligence/nic_signal_family_governance.json"
CHAMP=ROOT/"data/intelligence/nic_forecast_champion.json"
def load(p):
    try:
        v=json.loads(p.read_text())
        return v if isinstance(v,dict) else {}
    except Exception: return {}
def evidence(symbol, side):
    s=str(symbol or "").upper().replace("USDT","").strip()
    fs={"LONG":"BULLISH","SHORT":"BEARISH"}.get(str(side or "").upper(),"")
    if not fs:
        return {"symbol":s,"side":"","regime":"","trusted_cells":0,"max_lift":0.0,"evidence_score":0.0,
                "raw_evidence_score":0.0,"calibrated_probability":0.5,"probability_trusted":False,
                "advisory_only":True,"publish_gate_unchanged":True}
    results=load(LAB).get("results") or []
    current=next((r for r in results if isinstance(r,dict) and str(r.get("symbol") or "").upper()==s and r.get("status")=="READY"),{})
    regime=str(current.get("regime") or "")
    matrix=load(MATRIX).get("matrix") or {}
    cells=[r for r in matrix.values() if isinstance(r,dict) and str(r.get("side")).upper()==fs and str(r.get("regime"))==regime and r.get("trusted")]
    family=load(FAMILY_GOV).get("cells") or {}
    governed=[]
    for r in cells:
        feature=str(r.get("feature") or "")
        g=[x for x in family.values() if isinstance(x,dict) and str(x.get("feature"))==feature and str(x.get("side")).upper()==fs and str(x.get("regime"))==regime and int(x.get("horizon_hours") or 0)==int(r.get("horizon_hours") or 0)]
        if g:
            best=max(g,key=lambda x:int(x.get("samples") or 0))
            if str(best.get("state"))!="SUSPENDED":
                governed.append((r,best))
        else:
            governed.append((r,{"state":"RECOVERY","trust_multiplier":0.5}))
    lifts=[float(r.get("lift") or 0) for r,_ in governed]
    cal=load(CALIB).get("cells") or {}
    probs=[r for r in cal.values() if isinstance(r,dict) and str(r.get("side")).upper()==fs and str(r.get("regime"))==regime and r.get("trusted")]
    probability=(sum(float(r.get("calibrated_probability") or .5) for r in probs)/len(probs)) if probs else .5
    probability_trusted=bool(probs)
    champion_doc=load(CHAMP)
    champion=((champion_doc.get("selection") or {}).get("champion"))
    if probability_trusted and champion and champion != "BASELINE_RAW":
        transforms={"CONSERVATIVE":0.75,"CALIBRATED_SHRINK":0.60,"CONFIDENT":1.15}
        probability=0.5+(probability-0.5)*transforms.get(champion,1.0)
    probability=max(0.000001,min(0.999999,probability))
    governance=[]; gov=load(GOV).get("cells") or {}
    for key,row in gov.items():
        if isinstance(row,dict) and str(row.get("side")).upper()==fs and str(row.get("regime"))==regime:
            governance.append(row)
    governance_state="RECOVERY"; trust_multiplier=0.5
    if governance:
        best=max(governance,key=lambda x:int(x.get("horizon_hours") or 0))
        governance_state=str(best.get("state") or "RECOVERY")
        trust_multiplier=float(best.get("trust_multiplier") or 0.0)
    try:
        from nic_regime_transition import evaluate
        transition=evaluate(s)
    except Exception:
        transition={"transition_state":"UNKNOWN","regime_stability":0.0,"edge_decay_penalty":0.0,"usable":False}
    family_mult=sum(float(g.get("trust_multiplier") or 0.5) for _,g in governed)/len(governed) if governed else 0.0
    raw_score=min(12.0,4.0*len(governed)+max(0.0,max(lifts or [0]))*100)
    decay=float(transition.get("edge_decay_penalty") or 0)
    try:
        import sys
        if str(ROOT/"src") not in sys.path:
            sys.path.insert(0,str(ROOT/"src"))
        from nic_forecast_decision_policy import evaluate as evaluate_decision
        decision=evaluate_decision({"calibrated_probability":probability,"probability_trusted":probability_trusted,"evidence_score":round(raw_score*(1.0-decay)*trust_multiplier*family_mult,2),"regime_stability":transition.get("regime_stability",0.0),"edge_decay_penalty":decay,"side":fs})
    except Exception:
        decision={"decision":"WAIT","direction":"","confidence":0.0,"reasons":["decision_policy_unavailable"],"advisory_only":True,"publish_gate_unchanged":True}
    return {"symbol":s,"side":fs,"regime":regime,"trusted_cells":len(governed),"suspended_cells":len(cells)-len(governed),
            "max_lift":round(max(lifts or [0]),4),"evidence_score":round(raw_score*(1.0-decay)*trust_multiplier*family_mult,2),
            "raw_evidence_score":round(raw_score,2),"signal_family_trust_multiplier":round(family_mult,2),
            "calibrated_probability":round(probability,4),"probability_trusted":probability_trusted,"forecast_champion":champion or "NONE","decision_policy":decision,
            "regime_transition_state":transition.get("transition_state"),"regime_stability":transition.get("regime_stability",0.0),
            "edge_decay_penalty":decay,"governance_state":governance_state,"governance_trust_multiplier":round(trust_multiplier,2),
            "advisory_only":True,"publish_gate_unchanged":True}
if __name__=="__main__":
    print(json.dumps({"schema":"NIC-FORECAST-EVIDENCE-3.0","status":"READY","policy":"Resolved predictive evidence is regime- and signal-family-aware; it cannot override timing, diversity, cooldown, risk, visual truth, or publication gates."},indent=2))
