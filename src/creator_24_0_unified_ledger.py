"""Creator 24.0 — canonical publication/experiment ledger.

One durable row per verified publication joins the frozen opportunity, exact
published text, post id, audience observations, and trading-call state. This is
an aggregation layer: it never invents metrics or outcomes and does not alter
publication truth.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'analytics/publication_log.jsonl'
PERF=ROOT/'analytics/square_performance.jsonl'
CALLS=ROOT/'analytics/call_ledger.jsonl'
OUT=ROOT/'analytics/creator_24_0_ledger.jsonl'
REPORT=ROOT/'data/intelligence/creator_24_0_ledger_report.json'
CONTEXT=ROOT/'data/live/publication_context.json'
FROZEN=ROOT/'data/live/authoritative_opportunity.json'

def read_json(path, default):
    try:
        x=json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def jsonl(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def pid(x):
    return str(x.get('post_id') or x.get('id') or x.get('content_id') or '').strip()

def symbol(x):
    return str(x.get('symbol') or x.get('symbol_usdt') or '').upper().replace('$','').replace('USDT','')

def main():
    pubs=[x for x in jsonl(PUB) if pid(x) and str(x.get('status','')).startswith('PUBLISHED')]
    perf={pid(x):x for x in jsonl(PERF) if pid(x)}
    calls=jsonl(CALLS)
    call_by_symbol={symbol(x):x for x in calls if symbol(x)}
    ctx=read_json(CONTEXT,{})
    frozen=read_json(FROZEN,{})
    existing={pid(x) for x in jsonl(OUT)}
    now=datetime.now(timezone.utc).isoformat(); rows=[]
    for p in pubs:
        post=pid(p)
        row=dict(p)
        row['ledger_version']='24.0'
        row['ledger_updated_at']=now
        row['symbol']=symbol(p) or symbol(ctx) or symbol(frozen)
        row['category']=str(p.get('content_category') or p.get('category') or ctx.get('category') or frozen.get('category') or '')
        row['experiment_id']=str(p.get('experiment_id') or '')
        row['frozen_reference_price']=frozen.get('reference_price') or ctx.get('reference_price')
        row['frozen_trigger']=frozen.get('trigger') or frozen.get('entry')
        row['frozen_invalidation']=frozen.get('invalidation')
        row['performance']=perf.get(post)
        call=call_by_symbol.get(row['symbol'])
        row['call_state']=call if call and str(call.get('post_id') or '')==post else None
        if post not in existing:
            rows.append(row)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('a',encoding='utf-8') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    all_rows=jsonl(OUT)
    report={'version':'24.0','generated_at':now,'publication_count':len(pubs),'ledger_count':len(all_rows),'with_performance':sum(1 for x in all_rows if x.get('performance')),'with_call_state':sum(1 for x in all_rows if x.get('call_state')),'with_experiment':sum(1 for x in all_rows if x.get('experiment_id')),'principles':['One canonical row per verified post.','Never infer performance or revenue.','Frozen opportunity remains authoritative.','Ledger is read-only with respect to publication truth.']}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
