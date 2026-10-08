"""Resolve NIC decision outcomes from matured Forecast Laboratory truth records."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FORECAST=ROOT/"data/intelligence/nic_forecast_truth_ledger.jsonl"
DECISIONS=ROOT/"data/intelligence/nic_decision_outcome_ledger.jsonl"

def rows(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text().splitlines():
        try: out.append(json.loads(line))
        except: pass
    return out

def resolve(forecasts):
    now=datetime.now(timezone.utc); out=[]; seen=set()
    for x in forecasts:
        if not x.get("resolved"): continue
        fid=str(x.get("forecast_id") or "")
        if not fid or fid in seen: continue
        seen.add(fid)
        side=str(x.get("side") or "").upper()
        hit=bool(x.get("hit"))
        decision=str(x.get("decision") or ("LONG_CANDIDATE" if side=="BULLISH" else "SHORT_CANDIDATE"))
        aligned=(decision=="LONG_CANDIDATE" and side=="BULLISH") or (decision=="SHORT_CANDIDATE" and side=="BEARISH")
        if decision=="WAIT":
            outcome="ABSTAINED"; utility=0.25 if not hit else -0.10
        elif not aligned:
            outcome="DIRECTION_CONFLICT"; utility=-1.0
        else:
            outcome="WIN" if hit else "LOSS"; utility=1.0 if hit else -1.0
        out.append({"decision_id":fid,"forecast_id":fid,"timestamp":x.get("timestamp"),"resolved_at":x.get("resolved_at",now.isoformat()),"symbol":x.get("symbol"),"side":side,"decision":decision,"hit":hit,"outcome":outcome,"utility":utility})
    return out

def merge(existing,new):
    by={str(x.get("decision_id")):x for x in existing if x.get("decision_id")}
    by.update({str(x["decision_id"]):x for x in new})
    return list(by.values())

def summarize(rows_):
    r=[x for x in rows_ if x.get("outcome") not in {"UNRESOLVED",None}]
    active=[x for x in r if x.get("outcome") in {"WIN","LOSS"}]
    return {"samples":len(r),"utility":round(sum(float(x.get("utility",0)) for x in r)/len(r),6) if r else 0.0,
            "win_rate":round(sum(x.get("outcome")=="WIN" for x in active)/len(active),6) if active else None,
            "abstention_rate":round(sum(x.get("outcome")=="ABSTAINED" for x in r)/len(r),6) if r else None}

if __name__=="__main__":
    existing=rows(DECISIONS); new=resolve(rows(FORECAST)); merged=merge(existing,new)
    DECISIONS.parent.mkdir(parents=True,exist_ok=True)
    DECISIONS.write_text("\n".join(json.dumps(x,separators=(",",":")) for x in merged)+("\n" if merged else ""))
    print(json.dumps({"schema":"NIC-DECISION-OUTCOME-2.0","resolved_decisions":len(new),"summary":summarize(merged),"policy":"Decision outcomes are derived only from matured, resolved forecast truth; they remain advisory and cannot bypass publication gates."},indent=2))
