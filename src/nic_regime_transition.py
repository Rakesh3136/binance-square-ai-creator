"""NIC regime transition and edge-decay guard for forecast evidence."""
from __future__ import annotations
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HISTORY=ROOT/"data/intelligence/nic_regime_history.jsonl"
MATRIX=ROOT/"data/intelligence/nic_signal_predictivity_matrix.json"
MIN_OBS=4
def _read_jsonl(path):
    out=[]
    if not path.exists(): return out
    for line in path.read_text().splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out
def _n(v,d=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else d
    except Exception: return d
def _latest(rows):
    by={}
    for r in rows:
        s=str(r.get("symbol") or "").upper()
        if s: by.setdefault(s,[]).append(r)
    return {s:sorted(v,key=lambda x:str(x.get("timestamp") or "")) for s,v in by.items()}
def evaluate(symbol, history=None, matrix=None):
    s=str(symbol or "").upper().replace("USDT","").strip()
    rows=_latest(history if history is not None else _read_jsonl(HISTORY)).get(s,[])
    if len(rows)<MIN_OBS:
        return {"symbol":s,"transition_state":"UNKNOWN","regime_stability":0.0,"edge_decay_penalty":0.0,"usable":False}
    recent=rows[-min(4,len(rows)):]
    prior=rows[-min(8,len(rows)):-min(4,len(rows))]
    current=str(recent[-1].get("regime") or "UNKNOWN")
    prior_regs=[str(x.get("regime") or "UNKNOWN") for x in prior]
    prior_mode=max(set(prior_regs),key=prior_regs.count) if prior_regs else current
    stability=sum(str(x.get("regime") or "UNKNOWN")==current for x in recent)/len(recent)
    changed=current!=prior_mode
    transitions=sum(a!=b for a,b in zip([prior_mode]+[str(x.get("regime") or "UNKNOWN") for x in recent], [prior_mode]+[str(x.get("regime") or "UNKNOWN") for x in recent]))
    penalty=0.0
    if changed: penalty += 0.35
    if stability<0.75: penalty += 0.25
    penalty=min(1.0,penalty)
    cells=matrix if matrix is not None else (json.loads(MATRIX.read_text()).get("matrix") if MATRIX.exists() else {})
    lifts=[]
    for x in (cells or {}).values():
        if not isinstance(x,dict) or str(x.get("regime"))!=current or not x.get("trusted"): continue
        lifts.append(_n(x.get("recent_lift"),_n(x.get("lift"))))
    if lifts and max(lifts)<0: penalty=max(penalty,0.6)
    return {"symbol":s,"transition_state":"TRANSITION" if changed else ("UNSTABLE" if stability<0.75 else "STABLE"),
            "current_regime":current,"prior_regime":prior_mode,"regime_stability":round(stability,4),
            "edge_decay_penalty":round(penalty,4),"usable":True,"observations":len(rows),"transition_count":transitions}
def evaluate_all(history=None,matrix=None):
    rows=_latest(history if history is not None else _read_jsonl(HISTORY))
    return {s:evaluate(s,history=history,matrix=matrix) for s in rows}
if __name__=="__main__":
    print(json.dumps({"symbols":len(evaluate_all()),"schema":"NIC-REGIME-TRANSITION-1.0"}))
