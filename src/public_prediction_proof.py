"""Build a truthful follow-up opportunity from verified prediction outcomes.

This never changes an original call and never calls an open prediction a win.
It creates a content brief only when a terminal WIN/INVALIDATED result exists.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/public_prediction_proof.json'
OUTCOMES=ROOT/'analytics/prediction_outcomes.jsonl'
PUB=ROOT/'analytics/publication_log.jsonl'


def jsonl(path):
    if not path.exists(): return []
    rows=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): rows.append(x)
        except Exception: pass
    return rows


def main()->int:
    outcomes=jsonl(OUTCOMES); pubs={str(x.get('post_id')):x for x in jsonl(PUB) if x.get('post_id')}
    terminal=[x for x in outcomes if x.get('outcome') in {'WIN','INVALIDATED'}]
    terminal.sort(key=lambda x:str(x.get('evaluated_at','')), reverse=True)
    chosen=None
    for x in terminal:
        if x.get('outcome')=='WIN':
            chosen=x; break
    now=datetime.now(timezone.utc).isoformat()
    if not chosen:
        brief={'version':'1.0','generated_at':now,'status':'NO_VERIFIED_WIN','publishable':False,'reason':'No verified terminal WIN is available for a proof post.','next_step':'Continue normal opportunity selection; never manufacture a win.'}
    else:
        post_id=str(chosen.get('post_id') or '') or None
        original=pubs.get(post_id,{})
        brief={'version':'1.0','generated_at':now,'status':'VERIFIED_WIN_AVAILABLE','publishable':True,'proof_type':'PREDICTION_OUTCOME','call_id':chosen.get('call_id'),'post_id':post_id,'symbol':chosen.get('symbol'),'direction':chosen.get('direction'),'reference_price':chosen.get('reference_price'),'target':chosen.get('hit_target'),'evaluated_at':chosen.get('evaluated_at'),'original_publication_found':bool(original),'content_brief':f"Show the original {chosen.get('symbol')} {chosen.get('direction')} call, frozen reference/target, then the fresh Binance OHLCV evidence that confirmed the target. Clearly label the timestamps and avoid implying guaranteed future performance.",'next_hook':'After the verified result, invite readers to follow for the next evidence-backed setup; do not promise a pump.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(brief,indent=2,ensure_ascii=False)); return 0

if __name__=='__main__': raise SystemExit(main())
