"""Full-universe capital-flow scanner for Creator 7.x.

Scans the complete Binance USDT spot universe first, then performs bounded
higher-cost flow/structure enrichment on the most liquid and most unusual
assets. The goal is discovery before a coin becomes a top gainer, not chasing
an already-extended move. All values are observations; no future move is
claimed or guaranteed.
"""
from __future__ import annotations
import json, math, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/full_universe_flow.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com']
QUOTE='USDT'
ENRICH_N=120
DERIV_N=80
WORKERS=12

def get_json(path, params=None, futures=False):
    bases=['https://fapi.binance.com'] if futures else BASES
    q='?'+urllib.parse.urlencode(params or {}) if params else ''
    last=None
    for base in bases:
        try:
            req=urllib.request.Request(base+path+q,headers={'User-Agent':'binance-square-ai-creator/full-universe-flow','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as exc:last=exc
    return None

def num(v):
    try:return float(v)
    except Exception:return 0.0

def clean(s):return str(s or '').upper().replace('$','').replace('USDT','').strip()

def exchange_symbols():
    info=get_json('/api/v3/exchangeInfo',{'symbolStatus':'TRADING'}) or {}
    out=[]
    for x in info.get('symbols') or []:
        if x.get('status')!='TRADING' or x.get('quoteAsset')!=QUOTE or x.get('isSpotTradingAllowed') is False:continue
        s=str(x.get('symbol') or '')
        if s.endswith(QUOTE):out.append({'symbol':s,'asset':clean(s),'base_asset':x.get('baseAsset'),'quote_asset':x.get('quoteAsset')})
    return out

def spot_tickers():
    raw=get_json('/api/v3/ticker/24hr',{'type':'FULL'}) or []
    return {str(x.get('symbol')):x for x in raw if isinstance(x,dict)}

def klines(symbol):
    raw=get_json('/api/v3/klines',{'symbol':symbol,'interval':'1h','limit':25}) or []
    rows=[]
    for r in raw:
        if isinstance(r,list) and len(r)>=6:
            rows.append({'open_time':int(r[0]),'open':num(r[1]),'high':num(r[2]),'low':num(r[3]),'close':num(r[4]),'volume':num(r[5]),'quote_volume':num(r[7]) if len(r)>7 else 0.0})
    if len(rows)<8:return None
    vols=[x['quote_volume'] for x in rows[:-1] if x['quote_volume']>0]
    last=rows[-1]; baseline=sum(vols[-6:])/max(1,len(vols[-6:])); median=sorted(vols)[len(vols)//2] if vols else 0.0
    price_base=rows[-7]['close'] if rows[-7]['close'] else last['close']
    high=max(x['high'] for x in rows[-7:]); low=min(x['low'] for x in rows[-7:]);
    return {'last_1h_quote_volume':last['quote_volume'],'avg_prior_6h_quote_volume':baseline,'volume_acceleration':round(last['quote_volume']/baseline,3) if baseline else 0.0,'volume_vs_24h_median':round(last['quote_volume']/median,3) if median else 0.0,'price_change_6h_pct':round((last['close']-price_base)/price_base*100,3) if price_base else 0.0,'range_6h_pct':round((high-low)/last['close']*100,3) if last['close'] else 0.0,'close_position_6h':round((last['close']-low)/(high-low),3) if high>low else 0.5,'breakout_distance_pct':round((high-last['close'])/last['close']*100,3) if last['close'] else 0.0}

def derivatives(symbol):
    fs=symbol
    prem=get_json('/fapi/v1/premiumIndex',{'symbol':fs},True); hist=get_json('/futures/data/openInterestHist',{'symbol':fs,'period':'1h','limit':4},True)
    if not isinstance(prem,dict) and not isinstance(hist,list):return None
    r={}
    if isinstance(prem,dict):r['funding_rate']=num(prem.get('lastFundingRate'));r['mark_price']=num(prem.get('markPrice'))
    if isinstance(hist,list) and len(hist)>=2:
        old=num(hist[0].get('sumOpenInterestValue') or hist[0].get('sumOpenInterest'));new=num(hist[-1].get('sumOpenInterestValue') or hist[-1].get('sumOpenInterest'));r['oi_change_3h_pct']=round((new-old)/old*100,3) if old else 0.0
    return r or None

def score(row):
    vol=row.get('volume_acceleration',1.0); rel=row.get('relative_strength_24h',0.0); move=abs(row.get('price_change_percent',0)); rng=row.get('range_6h_pct',0); oi=row.get('oi_change_3h_pct',0); funding=abs(row.get('funding_rate',0))*10000; dist=row.get('breakout_distance_pct',99)
    s=0.0
    s+=min(30,max(0,(vol-1)*12))
    s+=min(18,max(0,rel*1.2))
    s+=min(12,max(0,(row.get('volume_vs_24h_median',1)-1)*5))
    s+=min(12,max(0,oi*1.5))
    s+=min(8,max(0,funding-2))
    s+=min(10,max(0,6-rng))
    s+=min(10,max(0,5-dist))
    if move>12:s-=18
    elif move>8:s-=10
    elif move>5:s-=5
    if row.get('close_position_6h',0)<0.35 and rel>0:s-=4
    return round(max(0,min(100,s)),2)

def main():
    universe=exchange_symbols();tickers=spot_tickers();rows=[]
    for u in universe:
        t=tickers.get(u['symbol']);
        if not t:continue
        pct=num(t.get('priceChangePercent'));qv=num(t.get('quoteVolume'));last=num(t.get('lastPrice'));high=num(t.get('highPrice'));low=num(t.get('lowPrice'))
        if qv<=0 or last<=0:continue
        rows.append({'symbol':u['asset'],'symbol_usdt':u['symbol'],'last_price':last,'price_change_percent':pct,'quote_volume_usdt':qv,'intraday_range_percent':round((high-low)/last*100,3) if last else 0.0})
    avg_market=sum(x['price_change_percent'] for x in rows)/max(1,len(rows));
    for x in rows:x['relative_strength_24h']=round(x['price_change_percent']-avg_market,3)
    # First-pass universe ranking is cheap and covers every live USDT spot asset.
    rows.sort(key=lambda x:(abs(x['relative_strength_24h']),math.log10(max(1,x['quote_volume_usdt']))),reverse=True)
    enrich=rows[:ENRICH_N]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(klines,x['symbol_usdt']):x for x in enrich}
        for f in as_completed(futs):
            try:
                k=f.result()
                if k:futs[f].update(k)
            except Exception:pass
    # Re-rank after volume/structure enrichment, then query derivatives only for the strongest 80.
    for x in enrich:x['discovery_score']=score(x)
    enrich.sort(key=lambda x:x['discovery_score'],reverse=True)
    deriv=enrich[:DERIV_N]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(derivatives,x['symbol_usdt']):x for x in deriv}
        for f in as_completed(futs):
            try:
                d=f.result()
                if d:futs[f].update(d)
            except Exception:pass
    for x in deriv:x['discovery_score']=score(x)
    enrich.sort(key=lambda x:x['discovery_score'],reverse=True)
    early=[]
    for x in enrich:
        # Prefer forming moves over already-parabolic movers.
        if x['discovery_score']<48 or abs(x.get('price_change_percent',0))>15:continue
        x['early_mover']=True;x['confirmation_required']=True;x['flow_state']='accelerating_participation' if x.get('volume_acceleration',0)>=1.5 else 'unusual_activity'
        x['evidence']=[k for k in ['volume_acceleration','volume_vs_24h_median','relative_strength_24h','oi_change_3h_pct','funding_rate','breakout_distance_pct'] if k in x]
        early.append(x)
    payload={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'OK','universe':{'spot_usdt_symbols':len(rows),'exchange_info_symbols':len(universe),'fully_enriched':len(enrich),'derivatives_enriched':len(deriv)},'market_breadth':{'average_24h_change':round(avg_market,4)},'early_movers':early[:40],'top_flow_candidates':enrich[:60],'all_live_symbols':[x['symbol'] for x in rows],'method':['Full Binance USDT spot universe from exchangeInfo','24h ticker breadth for every live symbol','1h volume acceleration and short-term structure for top 120 unusual/liquid assets','funding and open-interest context for top 80','relative strength versus market average','extension penalty to reduce late pump chasing'],'policy':['Discovery is not a prediction guarantee.','A candidate must be confirmed before a directional claim is published.','No asset is selected merely because it is a top gainer.','Missing flow evidence remains missing.','Order flow/funding/OI are context, not proof of whale activity or future price direction.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','spot_usdt_universe':len(rows),'fully_enriched':len(enrich),'derivatives_enriched':len(deriv),'early_movers':len(early),'top_candidate':early[0] if early else None},indent=2))
if __name__=='__main__':main()
