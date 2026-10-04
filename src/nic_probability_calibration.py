from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTCOMES=ROOT/'analytics/prediction_outcomes.jsonl'
OUT=ROOT/'data/live/nic_probability_calibration.json'
MIN_TOTAL=10
MIN_BIN=5

def rows(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def probability(row):
    for key in ('calibrated_confidence','model_confidence','confidence'):
        try:
            x=float(row.get(key)); x=x/100 if x>1 else x
            if math.isfinite(x) and 0<=x<=1: return x
        except (TypeError,ValueError): pass
    return None

def result(row):
    o=str(row.get('outcome') or '').upper()
    if o in {'WIN','TP1','TP2'}: return 1
    if o in {'INVALIDATED','LOSS','SL'}: return 0
    return None

def main():
    terminal={}
    ignored=0
    for row in rows(OUTCOMES):
        p=result(row); q=probability(row); eid=str(row.get('call_id') or row.get('prediction_id') or row.get('trade_id') or '').strip()
        if p is None or q is None or not eid: ignored+=1; continue
        terminal[eid]=(q,p)
    obs=list(terminal.values()); n=len(obs); wins=sum(y for _,y in obs)
    brier=sum((p-y)**2 for p,y in obs)/n if n else None
    log_loss=sum(-(y*math.log(max(p,1e-6))+(1-y)*math.log(max(1-p,1e-6))) for p,y in obs)/n if n else None
    bins=[]; weighted=0.0; totalq=0
    for i in range(10):
        m=[(p,y) for p,y in obs if min(9,int(p*10))==i]
        if not m: continue
        avg=sum(p for p,_ in m)/len(m); wr=sum(y for _,y in m)/len(m); gap=wr-avg; qualified=len(m)>=MIN_BIN
        if qualified: weighted+=abs(gap)*len(m); totalq+=len(m)
        bins.append({'range':f'{i*10}-{(i+1)*10}%','samples':len(m),'mean_predicted_probability':round(avg,4),'observed_win_rate':round(wr,4),'signed_calibration_gap':round(gap,4),'qualified_for_adjustment':qualified})
    mean_gap=weighted/totalq if totalq else None
    adj=0.0
    if n>=MIN_TOTAL and totalq:
        adj=sum(b['signed_calibration_gap']*b['samples'] for b in bins if b['qualified_for_adjustment'])/totalq
        adj=max(-0.10,min(0.10,adj))
    state='INSUFFICIENT_DATA' if n<MIN_TOTAL else ('CALIBRATED' if mean_gap is not None and mean_gap<=0.05 else ('NEEDS_RECALIBRATION' if mean_gap is not None and mean_gap<=0.10 else 'POORLY_CALIBRATED'))
    data={'schema':'NIC-PROBABILITY-CALIBRATION-1.0','generated_at':datetime.now(timezone.utc).isoformat(),'terminal_predictions':n,'wins':wins,'losses':n-wins,'ignored_nonterminal_or_unusable':ignored,'brier_score':round(brier,6) if brier is not None else None,'log_loss':round(log_loss,6) if log_loss is not None else None,'mean_absolute_calibration_gap':round(mean_gap,6) if mean_gap is not None else None,'recommended_probability_adjustment':round(adj,6),'state':state,'reliability_bins':bins,'policy':['Only terminal WIN/LOSS-style outcomes are evaluated.','Future outcomes never mutate historical prediction records.','Ambiguous outcomes are excluded from calibration.','Bins with fewer than 5 observations cannot drive an adjustment.','Calibration is advisory and cannot create, publish, or weaken a trade/risk gate.','Model confidence is not a guarantee or certainty claim.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8'); print(json.dumps(data,indent=2))
if __name__=='__main__': main()
