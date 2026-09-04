"""Creator 6.2 market-intelligence layer.

Builds a best-effort, evidence-only snapshot from public Binance spot/futures
market data plus the existing news/creator intelligence files. It does not invent
whale activity, token unlocks, creator calls, or private ranking signals.
"""
from __future__ import annotations
import json, os, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'
NEWS=ROOT/'data/live/news_snapshot.json'
CREATOR=ROOT/'data/live/creator_intelligence_report.json'
OUT=ROOT/'data/live/market_intelligence_6.json'
BASES=['https://fapi.binance.com','https://data-api.binance.vision','https://api.binance.com']


def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def get_json(base_path, params=None):
    query='?'+urllib.parse.urlencode(params or {}) if params else ''
    last=None
    for base in BASES:
        try:
            req=urllib.request.Request(base+base_path+query,headers={'User-Agent':'binance-square-ai-creator/6.2','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=12) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as exc:last=exc
    return None

def num(v):
    try:return float(v)
    except Exception:return 0.0

def clean(s):
    s=str(s or '').upper().replace('$','').replace('USDT','').strip()
    return s

def symbols_from_market(m):
    rows=[]
    seen=set()
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in m.get(group) or []:
            if not isinstance(x,dict):continue
            s=clean(x.get('symbol'))
            if s and s not in seen:
                seen.add(s);rows.append(s)
    return rows[:18]

def futures_symbol(s):return s+'USDT'

def funding_oi(symbol):
    fs=futures_symbol(symbol)
    premium=get_json('/fapi/v1/premiumIndex',{'symbol':fs})
    oi=get_json('/fapi/v1/openInterest',{'symbol':fs})
    hist=get_json('/fapi/v1/openInterestHist',{'symbol':fs,'period':'1h','limit':3})
    funding=get_json('/fapi/v1/fundingRate',{'symbol':fs,'limit':3})
    if not isinstance(premium,dict) and not isinstance(oi,dict) and not isinstance(hist,list) and not isinstance(funding,list):return None
    result={'symbol':symbol,'futures_symbol':fs}
    if isinstance(premium,dict):
        result['mark_price']=num(premium.get('markPrice'));result['index_price']=num(premium.get('indexPrice'));result['last_funding_rate']=num(premium.get('lastFundingRate'))
    if isinstance(oi,dict):result['open_interest']=num(oi.get('openInterest'))
    if isinstance(hist,list) and len(hist)>=2:
        old=num(hist[0].get('sumOpenInterest'));new=num(hist[-1].get('sumOpenInterest'));result['open_interest_change_1h_pct']=round((new-old)/old*100,4) if old else 0.0
    if isinstance(funding,list):result['funding_history']=[{'fundingRate':num(x.get('fundingRate')),'fundingTime':x.get('fundingTime')} for x in funding[-3:] if isinstance(x,dict)]
    return result

def orderbook(symbol):
    fs=futures_symbol(symbol)
    data=get_json('/fapi/v1/depth',{'symbol':fs,'limit':20})
    if not isinstance(data,dict):return None
    bids=sum(num(x[1]) for x in data.get('bids',[]) if isinstance(x,list) and len(x)>1)
    asks=sum(num(x[1]) for x in data.get('asks',[]) if isinstance(x,list) and len(x)>1)
    total=bids+asks
    return {'symbol':symbol,'bid_qty':bids,'ask_qty':asks,'orderbook_imbalance_pct':round((bids-asks)/total*100,2) if total else 0.0,'interpretation':'bid-heavy' if bids>asks*1.15 else 'ask-heavy' if asks>bids*1.15 else 'balanced'}

def main():
    market=load(MARKET);news=load(NEWS);creator=load(CREATOR);syms=symbols_from_market(market)
    derivatives=[];books=[]
    for s in syms[:12]:
        try:
            x=funding_oi(s)
            if x:derivatives.append(x)
        except Exception:pass
        try:
            x=orderbook(s)
            if x:books.append(x)
        except Exception:pass
    funding_extremes=sorted([x for x in derivatives if 'last_funding_rate' in x],key=lambda x:abs(x['last_funding_rate']),reverse=True)[:8]
    oi_accel=sorted([x for x in derivatives if 'open_interest_change_1h_pct' in x],key=lambda x:abs(x['open_interest_change_1h_pct']),reverse=True)[:8]
    imbalance=sorted(books,key=lambda x:abs(x['orderbook_imbalance_pct']),reverse=True)[:8]
    news_rows=[x for x in (news.get('articles') or []) if isinstance(x,dict)]
    material_news=[]
    for a in news_rows:
        score=num(a.get('news_score'))
        if score>=40:material_news.append({'title':str(a.get('title') or '')[:240],'source':a.get('source'),'url':a.get('url') or a.get('link'),'published_at':a.get('published_at'),'news_score':score,'symbols':a.get('symbols') or []})
    material_news=sorted(material_news,key=lambda x:x['news_score'],reverse=True)[:15]
    snapshot={'version':'6.2','generated_at':datetime.now(timezone.utc).isoformat(),'status':'OK','source_policy':'Public Binance spot/futures observations plus existing project snapshots. Missing signals remain missing.','coverage':{'spot_symbols_considered':len(syms),'derivative_symbols':len(derivatives),'orderbooks':len(books),'material_news':len(material_news)},'derivatives':derivatives,'funding_extremes':funding_extremes,'open_interest_acceleration':oi_accel,'orderbook_imbalance':imbalance,'material_news':material_news,'new_listings':market.get('new_listings') or [],'creator_intelligence_status':creator.get('status'),'available_creator_intelligence':creator.get('completed') or [],'signal_lanes':['breaking_news','macro','funding','open_interest','liquidations_proxy','orderbook_imbalance','top_gainers','top_losers','volume_anomaly','new_listing','creator_signal_outcome','education','comparison','follow_up'],'rules':['Funding and open interest are context, not automatic trade signals.','Orderbook imbalance is a short-lived observation, not proof of whale activity.','Do not label orderbook data as whale activity unless an actual whale-specific source exists.','Do not invent liquidation totals when no verified liquidation feed is available.','Do not invent token unlock dates; only use dates present in a verified input.','Creator calls/outcomes are only usable when the existing project intelligence supplies a verified record.','Macro stories must have a demonstrated crypto-market connection before outranking crypto-specific opportunities.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'6.2','symbols':len(syms),'derivatives':len(derivatives),'orderbooks':len(books),'material_news':len(material_news),'funding_extremes':len(funding_extremes),'oi_acceleration':len(oi_accel)},indent=2))

if __name__=='__main__':main()
