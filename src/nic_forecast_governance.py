"""NIC Adaptive Forecast Governance: controls trust from observed calibration quality."""
from __future__ import annotations
import json, math
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
CALIB=ROOT/"data/intelligence/nic_forecast_calibration.json"
OUT=ROOT/"data/intelligence/nic_forecast_governance.json"
MIN=30
WINDOW=30

def _rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text().splitlines():
        try:
            x=json.loads(line)
            if x.get("resolved") and x.get("forecast_probability") is not None and x.get("hit") is not None:
                out.append(x)
        except Exception: pass
    return sorted(out,key=lambda x:str(x.get("resolved_at") or x.get("timestamp") or ""))

def _clamp(v):
    return max(0.0,min(1.0,float(v)))

def _metrics(rows):
    if not rows: return {"samples":0,"brier_score":None,"log_loss":None}
    bs=ll=0.0
    for r in rows:
        p=_clamp(r.get("forecast_probability")); y=1.0 if r.get("hit") else 0.0
        bs+=(p-y)**2
        ll-=math.log(max(1e-6,p)) if y else math.log(max(1e-6,1-p))
    n=len(rows)
    return {"samples":n,"brier_score":round(bs/n,6),"log_loss":round(ll/n,6)}

def _state(rows):
    n=len(rows)
    if n<MIN: return "RECOVERY"
    recent=rows[-min(WINDOW,n):]
    hist=rows[:-len(recent)] if len(rows)>len(recent) else []
    rm=_metrics(recent); hm=_metrics(hist)
    # Calibration is useful only when recent scoring is not materially worse than history.
    if rm["brier_score"] is None: return "RECOVERY"
    if rm["brier_score"]>=0.25 or rm["log_loss"]>=0.69: return "SUSPENDED"
    if hist and rm["brier_score"] > hm["brier_score"] + 0.05: return "DEGRADED"
    return "TRUSTED"

def build():
    rows=_rows()
    cal=json.loads(CALIB.read_text()) if CALIB.exists() else {}
    groups={}
    for r in rows:
        k=(str(r.get("side") or "").upper(),str(r.get("regime") or "UNKNOWN"),int(r.get("horizon_hours") or 0))
        groups.setdefault(k,[]).append(r)
    cells={}
    for (side,reg,h),rs in groups.items():
        state=_state(rs)
        recent=_metrics(rs[-min(WINDOW,len(rs)):])
        multiplier={"TRUSTED":1.0,"DEGRADED":0.65,"RECOVERY":0.5,"SUSPENDED":0.0}[state]
        cells[f"{side}|{reg}|{h}h"]={
            "side":side,"regime":reg,"horizon_hours":h,"samples":len(rs),
            "state":state,"trust_multiplier":multiplier,
            "recent_metrics":recent,
            "recovery_required":state in {"RECOVERY","SUSPENDED"},
            "source_calibration_schema":cal.get("schema")
        }
    payload={
        "schema":"NIC-FORECAST-GOVERNANCE-1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "minimum_events":MIN,"rolling_window":WINDOW,"cells":cells,
        "policy":"Governance may downgrade forecast evidence when recent probabilistic quality degrades. SUSPENDED means no forecast trust multiplier. Recovery requires fresh resolved evidence; governance never overrides timing, diversity, cooldown, risk, visual truth, or publication gates."
    }
    OUT.write_text(json.dumps(payload,indent=2))
    return payload

if __name__=="__main__":
    p=build()
    print(json.dumps({"schema":p["schema"],"cells":len(p["cells"])}))
