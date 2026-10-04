"""NIC 23.2 — Adaptive experience engine.

Consumes immutable prediction/outcome records and produces conditional experience
profiles. It never rewrites historical predictions and never treats confidence as
probability of profit.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/'data/live/nic_trade_experience_ledger.json'
OUT=ROOT/'data/live/nic_adaptive_experience.json'
MIN_SAMPLES=25

def load(p):
    try:
        v=json.loads(p.read_text(encoding='utf-8'))
        return v if isinstance(v,dict) else {}
    except Exception:return {}

def main():
    doc=load(LEDGER); predictions=doc.get('predictions') if isinstance(doc.get('predictions'),list) else []
    outcomes=doc.get('outcomes') if isinstance(doc.get('outcomes'),list) else []
    by_id={str(x.get('prediction_id')):x for x in predictions if isinstance(x,dict) and x.get('prediction_id')}
    profiles=defaultdict(lambda:{'wins':0,'losses':0,'samples':0})
    for event in outcomes:
        if not isinstance(event,dict): continue
        p=by_id.get(str(event.get('prediction_id')))
        if not p: continue
        result=str(event.get('result') or '').upper()
        if result not in {'WIN','LOSS'}: continue
        key=(str(p.get('setup_type') or 'UNKNOWN').upper(),str(p.get('side') or 'UNKNOWN').upper(),str(p.get('timeframe') or 'UNKNOWN').upper(),str(p.get('market_regime') or 'UNKNOWN').upper())
        q=profiles[key]; q['samples']+=1; q['wins']+=result=='WIN'; q['losses']+=result=='LOSS'
    rows=[]
    for key,q in profiles.items():
        wr=q['wins']/q['samples'] if q['samples'] else None
        rows.append({'setup_type':key[0],'side':key[1],'timeframe':key[2],'market_regime':key[3],**q,'empirical_win_rate':round(wr,4) if wr is not None else None,'experience_status':'ESTABLISHED' if q['samples']>=MIN_SAMPLES else 'DEVELOPING'})
    result={'version':'23.2-adaptive-experience','generated_at':datetime.now(timezone.utc).isoformat(),'prediction_count':len(by_id),'outcome_count':len(outcomes),'profiles':rows,'policy':['Prediction records are immutable.','Outcomes are separate events.','Only terminal WIN/LOSS outcomes contribute to experience profiles.','Profiles never modify historical predictions.','Insufficient experience cannot authorize a trade.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\\n",encoding='utf-8'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
