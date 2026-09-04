"""Creator 6.2 market-intelligence layer.

Builds a best-effort, evidence-only snapshot from public Binance spot/futures
market data plus existing news/creator intelligence. It also enriches the live
market snapshot so the existing Content Director can rank derivatives context
without inventing prices or replacing real spot observations.
"""
from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; CREATOR=ROOT/'data/live/creator_intelligence_report.json'; OUT=ROOT/'data/live/market_intelligence_6.json'
BASES=['https://fapi.binance.com']

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def get_json(path,params=None):
    q='?'+urllib.parse.urlencode(params or {}) if params else ''
    for base in BASES:
        try:
            req=urllib.request.Request(base+path+q,headers={'User-Agent':'binance-square-ai-creator/6.2','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=12) as r:return json.loads(r.read().decode('utf-8'))
        except Exception:pass
    return None

def num(v):
    try:return float(v)
    except Exception:return 0.0

def clean(s):return str(s or '').upper().replace('$','').replace('USDT','').strip()

def symbols_from_market(m):
    out=[];seen=set()
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in m.get(group) or []:
            if isinstance(x,dict):
                s=clean(x.get('symbol'))
                if s and s not in seen:seen.add(s);out.append(s)
    return out[:18]

def funding_oi(s):
    fs=s+'USDT'; premium=get_json('/fapi/v1/premiumIndex',{'symbol':fs}); oi=get_json('/fapi/v1/openInterest',{'symbol':fs}); hist=get_json('/futures/data/openInterestHist',{'symbol':fs,'period':'1h','limit':3}); funding=get_json('/fapi/v1/fundingRate',{'symbol':fs,'limit':3})
    if not any(isinstance(x,(dict,list)) for x in (premium,oi,hist,funding)):return None
    r={'symbol':s,'futures_symbol':fs}
    if isinstance(premium,dict):r.update({'mark_price':num(premium.get('markPrice')),'index_price':num(premium.get('indexPrice')),'last_funding_rate':num(premium.get('lastFundingRate'))})
    if isinstance(oi,dict):r['open_interest']=num(oi.get('openInterest'))
    if isinstance(hist,list) and len(hist)>=2:
        old=num(hist[0].get('sumOpenInterest'));new=num(hist[-1].get('sumOpenInterest'));r['open_interest_change_1h_pct']=round((new-old)/old*100,4) if old else 0.0
    if isinstance(funding,list):r['funding_history']=[{'fundingRate':num(x.get('fundingRate')),'fundingTime':x.get('fundingTime')} for x in funding[-3:] if isinstance(x,dict)]
    return r

def orderbook(s):
    d=get_json('/fapi/v1/depth',{'symbol':s+'USDT','limit':20})
    if not isinstance(d,dict):return None
    bids=sum(num(x[1]) for x in d.get('bids',[]) if isinstance(x,list) and len(x)>1);asks=sum(num(x[1]) for x in d.get('asks',[]) if isinstance(x,list) and len(x)>1);total=bids+asks
    return {'symbol':s,'bid_qty':bids,'ask_qty':asks,'orderbook_imbalance_pct':round((bids-asks)/total*100,2) if total else 0.0,'interpretation':'bid-heavy' if bids>asks*1.15 else 'ask-heavy' if asks>bids*1.15 else 'balanced'}

def enrich_market(m,derivatives,books):
    dmap={x['symbol']:x for x in derivatives};bmap={x['symbol']:x for x in books}
    boostmap={}
    for s,x in dmap.items():
        boost=0.0; fr=abs(num(x.get('last_funding_rate'))); oi=abs(num(x.get('open_interest_change_1h_pct')))
        if fr>=0.001:boost+=5
        if fr>=0.003:boost+=5
        if oi>=3:boost+=5
        if oi>=8:boost+=5
        boostmap[s]=min(20.0,boost)
    for x in bmap.values():
        if abs(num(x.get('orderbook_imbalance_pct')))>=25:boostmap[x['symbol']]=min(20.0,boostmap.get(x['symbol'],0)+3)
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for row in m.get(group) or []:
            s=clean(row.get('symbol'))
            if not s:continue
            if s in dmap:row['derivatives_context']=dmap[s]
            if s in bmap:row['orderbook_context']=bmap[s]
            if s in boostmap:row['intelligence_signal_boost']=round(boostmap[s],2);row['content_signal_score']=round(min(100.0,num(row.get('content_signal_score'))+boostmap[s]),2)
    m['intelligence_version']='6.2';m['intelligence_generated_at']=datetime.now(timezone.utc).isoformat();m['intelligence_signal_policy']='Derivatives/orderbook observations enrich ranking; they never replace spot price, volume or candles.'

def main():
    market=load(MARKET);news=load(NEWS);creator=load(CREATOR);syms=symbols_from_market(market);derivatives=[];books=[]
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
    material_news=[]
    for a in (news.get('articles') or []):
        if not isinstance(a,dict):continue
        score=num(a.get('news_score'))
        if score>=40:material_news.append({'title':str(a.get('title') or '')[:240],'source':a.get('source'),'url':a.get('url') or a.get('link'),'published_at':a.get('published_at'),'news_score':score,'symbols':a.get('symbols') or []})
    material_news=sorted(material_news,key=lambda x:x['news_score'],reverse=True)[:15]
    enrich_market(market,derivatives,books)
    MARKET.write_text(json.dumps(market,indent=2,ensure_ascii=False),encoding='utf-8')
    snapshot={'version':'6.2','generated_at':datetime.now(timezone.utc).isoformat(),'status':'OK','source_policy':'Public Binance futures observations plus existing project snapshots. Missing signals remain missing.','coverage':{'spot_symbols_considered':len(syms),'derivative_symbols':len(derivatives),'orderbooks':len(books),'material_news':len(material_news)},'derivatives':derivatives,'funding_extremes':funding_extremes,'open_interest_acceleration':oi_accel,'orderbook_imbalance':imbalance,'material_news':material_news,'new_listings':market.get('new_listings') or [],'creator_intelligence_status':creator.get('status'),'available_creator_intelligence':creator.get('completed') or [],'signal_lanes':['breaking_news','macro','funding','open_interest','liquidations_proxy','orderbook_imbalance','top_gainers','top_losers','volume_anomaly','new_listing','creator_signal_outcome','education','comparison','follow_up'],'rules':['Funding and open interest are context, not automatic trade signals.','Orderbook imbalance is a short-lived observation, not proof of whale activity.','Do not label orderbook data as whale activity without a whale-specific source.','Do not invent liquidation totals when no verified liquidation feed is available.','Do not invent token unlock dates; only use dates present in verified input.','Creator calls/outcomes are usable only when existing project intelligence supplies a verified record.','Macro stories need a demonstrated crypto-market connection before outranking crypto-specific opportunities.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'6.2','symbols':len(syms),'derivatives':len(derivatives),'orderbooks':len(books),'material_news':len(material_news),'funding_extremes':len(funding_extremes),'oi_acceleration':len(oi_accel)},indent=2))
if __name__=='__main__':main()
