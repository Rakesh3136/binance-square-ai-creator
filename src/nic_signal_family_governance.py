"""NIC Signal-Family Edge Governance: adaptive trust for individual forecast features."""
from __future__ import annotations
import json, math
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
OUT=ROOT/"data/intelligence/nic_signal_family_governance.json"
MIN=30; WINDOW=20

def rows():
    if not LEDGER.exists(): return []
    out=[]
    for line in LEDGER.read_text().splitlines():
        try:
            x=json.loads(line)
            if x.get("resolved") and x.get("feature") and x.get("hit") is not None: out.append(x)
        except Exception: pass
    return sorted(out,key=lambda x:str(x.get("resolved_at") or x.get("timestamp") or ""))

def metric(rs):
    if not rs:return {"samples":0,"hit_rate":None}
    return {"samples":len(rs),"hit_rate":round(sum(bool(x.get("hit")) for x in rs)/len(rs),4)}

def build():
    groups={}
    for r in rows():
        key=(str(r.get("feature") or "UNKNOWN"),str(r.get("side") or "").upper(),str(r.get("regime") or "UNKNOWN"),int(r.get("horizon_hours") or 0))
        groups.setdefault(key,[]).append(r)
    cells={}
    for (feature,side,regime,h),rs in groups.items():
        n=len(rs); recent=rs[-min(WINDOW,n):]
        hit=sum(bool(x.get("hit")) for x in rs)/n
        rh=sum(bool(x.get("hit")) for x in recent)/len(recent)
        state="RECOVERY"
        if n>=MIN:
            if hit<0.50 or rh<hit-0.10: state="SUSPENDED"
            elif rh<hit-0.05: state="DEGRADED"
            else: state="TRUSTED"
        mult={"TRUSTED":1.0,"DEGRADED":0.65,"RECOVERY":0.5,"SUSPENDED":0.0}[state]
        cells[f"{feature}|{side}|{regime}|{h}h"]={"feature":feature,"side":side,"regime":regime,"horizon_hours":h,"samples":n,"historical_hit_rate":round(hit,4),"recent_hit_rate":round(rh,4),"state":state,"trust_multiplier":mult}
    payload={"schema":"NIC-SIGNAL-FAMILY-GOVERNANCE-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"minimum_events":MIN,"rolling_window":WINDOW,"cells":cells,"policy":"Feature-level trust adapts to resolved outcomes. A weak or collapsing signal family is downgraded or suspended; this is advisory and cannot bypass timing, diversity, cooldown, risk, visual truth, or publication gates."}
    OUT.write_text(json.dumps(payload,indent=2)); return payload
if __name__=="__main__":
    p=build(); print(json.dumps({"schema":p["schema"],"cells":len(p["cells"])}))
