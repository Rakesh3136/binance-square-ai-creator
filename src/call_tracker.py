"""Verified prediction ledger and outcome engine.

Records only explicit, machine-readable calls with a reference price/time and
optional target/invalidation. It never guarantees an outcome or fabricates a hit.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/'analytics/call_ledger.jsonl'
SUMMARY=ROOT/'data/intelligence/call_tracker.json'


def load_json(path, default):
    try:
        x=json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
        return x if isinstance(x,dict) else default
    except Exception:return default

def num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def main():
    context=load_json('data/live/publication_context.json',{})
    draft=load_json('data/live/creator_status.json',{})
    symbol=str(context.get('symbol_usdt') or context.get('symbol') or '').upper()
    # The technical enricher is the authoritative source for numerical levels.
    tech=load_json('data/live/technical_enrichment.json',{})
    price=num(tech.get('reference_price') or tech.get('current_price') or context.get('reference_price'))
    targets=tech.get('targets') if isinstance(tech.get('targets'),list) else []
    invalidation=num(tech.get('invalidation') or tech.get('stop_loss') or tech.get('sl'))
    explicit=bool(price and (targets or invalidation))
    record={
      'recorded_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'reference_price':price,
      'targets':[num(x) for x in targets if num(x) is not None],'invalidation':invalidation,
      'status':'OPEN' if explicit else 'NO_EXPLICIT_CALL','verification':'unverified_until_fresh_market_data_confirms_target_or_invalidation',
      'source':'verified technical enrichment + frozen publication context'
    }
    if explicit:
        record['call_id']=f"{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        LEDGER.parent.mkdir(parents=True,exist_ok=True)
        with LEDGER.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    open_calls=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding='utf-8').splitlines():
            try:
                r=json.loads(line)
                if r.get('status')=='OPEN':open_calls.append(r)
            except Exception:pass
    SUMMARY.parent.mkdir(parents=True,exist_ok=True)
    SUMMARY.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'latest':record,'open_calls':open_calls,'rules':['Never claim a target was hit without fresh verified market data.','Never rewrite reference price, target or invalidation after publication.','A failed setup is reported as invalidated rather than hidden.']},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))

if __name__=='__main__':main()
