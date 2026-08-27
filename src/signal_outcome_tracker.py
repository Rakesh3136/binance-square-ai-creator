import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BENCH=ROOT/'data/intelligence/creator_benchmark.json'
MARKET=ROOT/'data/live/market_snapshot.json'
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
WATCH=ROOT/'data/intelligence/signal_watchlist.json'
SIGNAL_RE=re.compile(r'\b(breakout|breaks? out|target|tp\b|stop[- ]?loss|sl\b|support|resistance|entry|buy|long|bullish|10x|20x|squeeze)\b',re.I)
CASHTAG_RE=re.compile(r'\$([A-Z][A-Z0-9]{1,11})\b')

def load(p, default=None):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,type(default if default is not None else {})) else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}

def market_price(market, symbol):
    target=symbol.upper()+'USDT'
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get('symbol','')).upper()==target:
                try:return float(x.get('last_price'))
                except Exception:return None
    return None

def parse_signal(post):
    text=str(post.get('content') or post.get('title') or '')
    if not SIGNAL_RE.search(text): return None
    symbols=[]
    for s in CASHTAG_RE.findall(text.upper()):
        if s not in symbols: symbols.append(s)
    if not symbols: return None
    return {'post_id':str(post.get('id') or ''),'author':str(post.get('authorName') or ''),'link':str(post.get('webLink') or ''),'text':text[:1200],'symbol':symbols[0],'observed_at':datetime.now(timezone.utc).isoformat(),'baseline_price':None,'status':'WATCHING'}

def main():
    bench=load(BENCH,{})
    market=load(MARKET,{})
    watch=load(WATCH,{'signals':[]})
    signals=watch.get('signals') if isinstance(watch.get('signals'),list) else []
    by_id={str(x.get('post_id')):x for x in signals if x.get('post_id')}
    for post in bench.get('top_posts') or []:
        if not isinstance(post,dict): continue
        sig=parse_signal(post)
        if not sig: continue
        sig['baseline_price']=market_price(market,sig['symbol'])
        key=sig['post_id'] or f"{sig['author']}:{sig['symbol']}:{sig['text'][:80]}"
        by_id[key]={**by_id.get(key,{}),**sig}
    for key,row in list(by_id.items()):
        if row.get('status')!='WATCHING': continue
        base=row.get('baseline_price'); now=market_price(market,str(row.get('symbol','')))
        if base and now:
            row['current_price']=now
            row['change_percent']=round((now/base-1)*100,2)
            row['checked_at']=datetime.now(timezone.utc).isoformat()
            if row['change_percent']>=20: row['status']='CONFIRMED_MOVE'
            elif row['change_percent']<=-15: row['status']='FAILED_MOVE'
    rows=list(by_id.values())[-200:]
    WATCH.parent.mkdir(parents=True,exist_ok=True)
    WATCH.write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'signals':rows},indent=2,ensure_ascii=False),encoding='utf-8')
    winners=[x for x in rows if x.get('status')=='CONFIRMED_MOVE' and x.get('change_percent') is not None]
    winners.sort(key=lambda x:abs(float(x.get('change_percent') or 0)),reverse=True)
    if winners and PREFLIGHT.exists():
        w=winners[0]
        pre=load(PREFLIGHT,{})
        pre['run_ai']=True
        pre['reason']='verified_creator_signal_outcome'
        pre['selected_opportunity']={'category':'creator_signal_outcome','symbol':w['symbol']+'USDT','reason':'A public creator signal previously observed in the benchmark feed has a verified subsequent move.','source_creator':w.get('author'),'source_post_url':w.get('link'),'source_post_id':w.get('post_id'),'baseline_price':w.get('baseline_price'),'current_price':w.get('current_price'),'change_percent':w.get('change_percent'),'instruction':f"Write a verified outcome update for ${w['symbol']}. State that a public creator previously discussed the setup only if the stored source post supports it. Report the observed move of {w['change_percent']:+.2f}% from the stored baseline. Do not claim we predicted it. Do not invent a target, entry, SL, or 10x outcome. Use the source post link only as attribution context."}
        pre['follow_up_context']={'type':'creator_signal_outcome','source_creator':w.get('author'),'source_post_url':w.get('link'),'symbol':w['symbol'],'change_percent':w.get('change_percent')}
        PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','watched_signals':len(rows),'confirmed_outcomes':len(winners),'selected_follow_up':winners[0]['symbol'] if winners else None},indent=2))

if __name__=='__main__': main()
