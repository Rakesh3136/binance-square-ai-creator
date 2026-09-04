from __future__ import annotations
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRE=ROOT/'data/live/editorial_preflight.json'; ENGAGEMENT=ROOT/'data/live/engagement_strategy.json'; MARKET=ROOT/'data/live/market_snapshot.json'; OUT=ROOT/'data/live/authoritative_opportunity.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com']
def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def symbol(v):
    if not isinstance(v,dict): return ''
    for k in ('symbol','selected_lane_symbol','topic'):
        raw=str(v.get(k) or '').upper().strip().replace('BINANCE:','')
        if raw:return raw if raw.endswith('USDT') else raw+'USDT'
    return ''
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'binance-square-ai-creator/3.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as h:return json.loads(h.read().decode('utf-8'))
def trading_symbols():
    last=None
    for b in BASES:
        try:
            d=fetch(b+'/api/v3/exchangeInfo?symbolStatus=TRADING')
            return {str(x.get('symbol','')).upper() for x in d.get('symbols',[]) if str(x.get('status','')).upper()=='TRADING'}
        except Exception as e:last=e
    raise RuntimeError(f'Unable to verify Binance trading symbols: {last}')
def main():
    pre=load(PRE); eng=load(ENGAGEMENT); market=load(MARKET)
    selected=pre.get('selected_opportunity') or {}; selected=selected if isinstance(selected,dict) else {}
    news_authoritative=bool(selected.get('news_title') and (selected.get('news_override') or selected.get('type')=='news' or selected.get('category') in {'breaking_news','news_and_macro','news_market_impact'}))
    if news_authoritative:
        chosen=dict(selected); source='preflight_news_override'
    else:
        pool=[]
        for x in [eng.get('selected')]+(eng.get('ranked_candidates') or []):
            if isinstance(x,dict):pool.append(x)
        for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
            for x in market.get(key) or []:
                if isinstance(x,dict):pool.append(x)
        valid=trading_symbols(); seen=set(); chosen=None
        for x in pool:
            s=symbol(x)
            if s and s not in seen:
                seen.add(s)
                if s in valid:
                    chosen=x; break
        source='validated_engagement_or_market_candidate'
    if not chosen or not symbol(chosen):raise SystemExit('No selected opportunity to freeze')
    usdt=symbol(chosen); valid=trading_symbols()
    if usdt not in valid:raise SystemExit(f'Frozen opportunity is not a currently trading Binance symbol: {usdt}')
    sym=usdt[:-4]; chosen=dict(chosen); chosen['symbol']=usdt
    pre['selected_opportunity']=chosen
    frozen={'version':5,'frozen_at':datetime.now(timezone.utc).isoformat(),'symbol':sym,'symbol_usdt':usdt,'binance_verified':True,'category':chosen.get('category',''),'reason':chosen.get('reason',''),'instruction':chosen.get('instruction',''),'score':chosen.get('engagement_score',chosen.get('adjusted_score',chosen.get('raw_score',0))),'run_ai':bool(pre.get('run_ai',False)),'selection_source':source,'news_authoritative':news_authoritative,'news_title':chosen.get('news_title',''),'news_source':chosen.get('news_source',chosen.get('source',''))}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(frozen,indent=2,ensure_ascii=False),encoding='utf-8'); PRE.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(frozen,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
