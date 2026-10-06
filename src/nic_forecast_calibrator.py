"""NIC Forecast probability calibration from resolved, regime-matched outcomes."""
from __future__ import annotations
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
OUT=ROOT/"data/intelligence/nic_forecast_calibration.json"
H=(6,12,24); MIN=30
def read():
    if not LEDGER.exists(): return []
    rows=[]
    for line in LEDGER.read_text().splitlines():
        try:
            x=json.loads(line)
            if x.get("resolved") and int(x.get("horizon_hours") or 0) in H: rows.append(x)
        except Exception: pass
    return rows
def calibrate():
    groups={}
    for x in read():
        k=(str(x.get("side") or "").upper(),str(x.get("regime") or "UNKNOWN"),int(x.get("horizon_hours") or 0))
        groups.setdefault(k,[]).append(float(x.get("signed_return") or 0))
    cells={}
    for (side,reg,h),vals in groups.items():
        wins=sum(v>0 for v in vals); n=len(vals)
        # Laplace/Beta smoothing prevents tiny samples from masquerading as certainty.
        p=(wins+1)/(n+2)
        confidence=min(1.0,n/MIN)
        calibrated=0.5+(p-0.5)*confidence
        cells[f"{side}|{reg}|{h}h"]={"side":side,"regime":reg,"horizon_hours":h,"samples":n,
            "wins":wins,"raw_rate":round(wins/n,4),"calibrated_probability":round(calibrated,4),
            "confidence":round(confidence,4),"trusted":n>=MIN}
    OUT.write_text(json.dumps({"schema":"NIC-FORECAST-CALIBRATION-1.0",
        "minimum_events":MIN,"cells":cells,
        "policy":"Probabilities are calibrated from resolved outcomes; small samples are shrunk toward 50% and are never presented as trusted."},indent=2))
    return cells
if __name__=="__main__":
    print(json.dumps({"cells":len(calibrate())}))
