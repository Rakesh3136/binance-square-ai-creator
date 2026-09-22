"""Persist lightweight judge calibration/disagreement statistics.

This is observational only: it never changes a trade contract or publication gate.
"""
from __future__ import annotations
import json
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data/live'; OUT=LIVE/'decision_calibration.json'; HISTORY=ROOT/'analytics/decision_judge_history.jsonl'

def load(name):
    try: return json.loads((LIVE/name).read_text(encoding='utf-8'))
    except Exception: return {}

def main():
    ens=load('decision_ensemble.json'); votes=ens.get('votes') or []
    rows=[]
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding='utf-8').splitlines()[-500:]:
            try: rows.append(json.loads(line))
            except Exception: pass
    rows.append({'at':datetime.now(timezone.utc).isoformat(),'symbol':ens.get('symbol'),'decision':ens.get('decision'),'votes':votes})
    HISTORY.parent.mkdir(parents=True,exist_ok=True)
    HISTORY.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows[-500:])+'\n',encoding='utf-8')
    stats=defaultdict(Counter)
    for row in rows:
        for v in row.get('votes') or []:
            stats[str(v.get('agent') or 'unknown')][str(v.get('decision') or 'UNKNOWN')]+=1
    result={'version':'1.0','updated_at':datetime.now(timezone.utc).isoformat(),'samples':len(rows),'current_disagreement':bool(ens.get('disagreement')),'agent_decision_counts':{k:dict(v) for k,v in stats.items()},'policy':'Calibration is observational until enough verified outcomes exist; it cannot override deterministic gates.'}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
