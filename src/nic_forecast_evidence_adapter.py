"""NIC Forecast evidence adapter: exposes only resolved, regime-matched predictive edge to downstream ranking."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/"data/live/nic_forecast_laboratory.json"
MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
CALIB=ROOT/"data/intelligence/nic_forecast_calibration.json"
def load(p):
    try:
        v=json.loads(p.read_text())
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}
def evidence(symbol, side):
    s=str(symbol or "").upper().replace("USDT","").strip()
    fs={"LONG":"BULLISH","SHORT":"BEARISH"}.get(str(side or "").upper(),"")
    results=load(LAB).get("results") or []
    current=next((r for r in results if isinstance(r,dict) and str(r.get("symbol") or "").upper()==s and r.get("status")=="READY"),{})
    regime=str(current.get("regime") or "")
    matrix=load(MATRIX).get("matrix") or {}
    cells=[r for r in matrix.values() if isinstance(r,dict) and str(r.get("side")).upper()==fs and str(r.get("regime"))==regime and r.get("trusted")]
    lifts=[float(r.get("lift") or 0) for r in cells]
    return {"symbol":s,"side":fs,"regime":regime,"trusted_cells":len(cells),
            "max_lift":round(max(lifts or [0]),4),
            "evidence_score":round(min(12.0,4.0*len(cells)+max(0.0,max(lifts or [0]))*100),2),"calibrated_probability":probability,"probability_trusted":bool(probs),
            "advisory_only":True,"publish_gate_unchanged":True}
if __name__=="__main__":
    print(json.dumps({"schema":"NIC-FORECAST-EVIDENCE-1.0","status":"READY","policy":"Resolved predictive evidence may rank candidates but cannot override timing, diversity, cooldown, or publication gates."},indent=2))
