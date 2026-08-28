from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
PRE=ROOT/'data/live/editorial_preflight.json'
OUT=ROOT/'data/live/authoritative_opportunity.json'

def main():
    data=json.loads(PRE.read_text(encoding='utf-8'))
    selected=data.get('selected_opportunity') or {}
    if not selected.get('symbol'):
        raise SystemExit('No selected opportunity to freeze')
    frozen={
        'version':1,
        'frozen_at':datetime.now(timezone.utc).isoformat(),
        'symbol':str(selected.get('symbol')).upper().replace('USDT',''),
        'symbol_usdt':str(selected.get('symbol')).upper().replace('USDT','')+'USDT',
        'category':selected.get('category',''),
        'reason':selected.get('reason',''),
        'instruction':selected.get('instruction',''),
        'score':selected.get('adjusted_score',selected.get('raw_score',0)),
        'run_ai':bool(data.get('run_ai',False)),
    }
    OUT.write_text(json.dumps(frozen,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(frozen,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
