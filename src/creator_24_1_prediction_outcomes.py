"""Creator 24.1 — fresh-data prediction outcome verifier.

Evaluates OPEN calls against fresh Binance 1H candles. A call can only become
WIN, LOSS or INVALIDATED when the candle path objectively crosses the frozen
levels. Ambiguous candles remain OPEN. The original prediction is immutable.
"""
from __future__ import annotations
import json, urllib.parse, urllib.request, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; LEDGER=ROOT/'analytics/call_ledger.jsonl'; OUT=ROOT/'analytics/prediction_outcomes.jsonl'; SUMMARY=ROOT/'data/intelligence/prediction_outcomes.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com']

def num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def candles(symbol):
    q=urllib.parse.urlencode({'symbol':symbol+'USDT','interval':'1h','limit':3})
    last=None
    for base in BASES:
        try:
            req=urllib.request.Request(base+'/api/v3/klines?'+q,headers={'User-Agent':'binance-square-ai-creator/24.1','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as e:last=e
    raise RuntimeError(str(last))

def main():
    calls=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding='utf-8').splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict) and x.get('status')=='OPEN':calls.append(x)
            except Exception:pass
    now=datetime.now(timezone.utc).isoformat(); outcomes=[]; errors=[]
    existing_ids=set()
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8').splitlines():
            try:
                x=json.loads(line); existing_ids.add(str(x.get('call_id') or ''))
            except Exception:pass
    for call in calls:
        cid=str(call.get('call_id') or ''); symbol=str(call.get('symbol') or '').upper(); direction=str(call.get('direction') or '').upper(); targets=[num(x) for x in call.get('targets',[]) if num(x) is not None]; inv=num(call.get('invalidation')); ref=num(call.get('reference_price'))
        if not cid or not symbol or ref is None or not targets or inv is None:continue
        try: raw=candles(symbol)
        except Exception as e:errors.append({'call_id':cid,'error':str(e)});continue
        highs=[num(r[2]) for r in raw if isinstance(r,list) and len(r)>4]; lows=[num(r[3]) for r in raw if isinstance(r,list) and len(r)>4]
        if not highs or not lows:continue
        outcome='OPEN'; hit_target=None; reason='no frozen level crossed in observed candles'
        if direction.startswith('SHORT'):
            if any(h is not None and h>=inv for h in highs): outcome='INVALIDATED'; reason='fresh candle high crossed frozen invalidation'
            else:
                for t in targets:
                    if any(l is not None and l<=t for l in lows): hit_target=t; break
                if hit_target is not None: outcome='WIN'; reason='fresh candle low crossed frozen target'
        else:
            if any(l is not None and l<=inv for l in lows): outcome='INVALIDATED'; reason='fresh candle low crossed frozen invalidation'
            else:
                for t in targets:
                    if any(h is not None and h>=t for h in highs): hit_target=t; break
                if hit_target is not None: outcome='WIN'; reason='fresh candle high crossed frozen target'
        if outcome!='OPEN' and cid in existing_ids:continue
        row={'evaluated_at':now,'call_id':cid,'post_id':call.get('post_id'),'symbol':symbol,'direction':direction,'reference_price':ref,'targets':targets,'invalidation':inv,'observed_high':max(highs),'observed_low':min(lows),'outcome':outcome,'hit_target':hit_target,'reason':reason,'source':'fresh Binance 1H OHLCV','prediction_immutable':True}
        outcomes.append(row)
    if outcomes:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('a',encoding='utf-8') as f:
            for x in outcomes:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    all_rows=[]
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8').splitlines():
            try:all_rows.append(json.loads(line))
            except Exception:pass
    terminal=[x for x in all_rows if x.get('outcome') in {'WIN','LOSS','INVALIDATED'}]
    report={'version':'24.1','checked_at':now,'open_calls_seen':len(calls),'new_outcomes':len(outcomes),'wins':sum(x.get('outcome')=='WIN' for x in all_rows),'invalidated':sum(x.get('outcome')=='INVALIDATED' for x in all_rows),'terminal_outcomes':len(terminal),'errors':errors,'rules':['No guarantee is inferred.','Ambiguous paths remain OPEN.','Frozen reference/targets/invalidation are immutable.','No result is declared without fresh Binance OHLCV.']}
    SUMMARY.parent.mkdir(parents=True,exist_ok=True);SUMMARY.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    # Turn only verified wins into a downstream proof-content brief. Failure of
    # this optional brief must never invalidate the market outcome calculation.
    try: subprocess.run(['python',str(ROOT/'src/public_prediction_proof.py')],cwd=ROOT,check=False)
    except Exception: pass
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
