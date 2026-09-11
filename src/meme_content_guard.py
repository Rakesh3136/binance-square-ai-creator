"""Small guard for the existing meme lane.

Memes may support audience growth, but they cannot create or modify a trading call.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MEME=ROOT/'data/live/meme_content_brief.json'
FLOW=ROOT/'data/live/capital_flow_intelligence.json'
PROOF=ROOT/'data/live/public_prediction_proof.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def main()->int:
    flow=load(FLOW); proof=load(PROOF)
    leaders=flow.get('leaders') or []
    theme='market_rotation' if leaders else 'market_reaction'
    brief={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'content_lane':'MEME','trading_call_allowed':False,'theme':theme,'rotation_reference':[x.get('symbol') for x in leaders[:3] if isinstance(x,dict)],'proof_reference':proof.get('call_id') if proof.get('status')=='VERIFIED_WIN_AVAILABLE' else None,'rules':['Original meme only; no copied template claims.','Never state a meme is a trading signal.','Never create, alter or overwrite entry, target, stop or invalidation.','Use verified market observations only when mentioning assets.']}
    MEME.parent.mkdir(parents=True,exist_ok=True);MEME.write_text(json.dumps(brief,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(brief,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
