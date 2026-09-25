"""Full-universe early participation scanner for Creator 7.x.

The first pass covers every live Binance USDT spot symbol. Only the bounded
second pass is expensive. Candidates are classified as EARLY/DEVELOPING/
CONFIRMED/LATE/EXHAUSTED so the publisher can refuse to turn an unconfirmed
observation into a prediction. No future move is guaranteed.
"""
from __future__ import annotations
import json, math, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/full_universe_flow.json'
STATE=ROOT/'data/live/full_universe_flow_state.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com']
QUOTE='USDT'; ENRICH_N=120; DERIV_N=80; WORKERS=12

def get_json(path,params=None,futures=False):
    bases=['https://fapi.binance.com'] if futures else BASES
    q='?'+urllib.parse.urlencode(params or {}) if params else ''
    for base in bases:
        try:
            req=urllib.request.Request(base+path+q,headers={'User-Agent':'binance-square-ai-creator/full-universe-flow','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode('utf-8'))
        except Exception:pass
    return None

def num(v):
    try:return float(v)
    except Exception:return 0.0

def clean(s):return str(s or '').upper().replace('$','').replace('USDT','').strip()

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}

def exchange_symbols():
    info=get_json('/api/v3/exchangeInfo',{'symbolStatus':'TRADING'}) or {}
    return [{'symbol':str(x.get('symbol')),'asset':clean(x.get('symbol')),'base_asset':x.get('baseAsset'),'quote_asset':x.get('quoteAsset')}
            for x in info.get('symbols') or [] if x.get('status')=='TRADING' and x.get('quoteAsset')==QUOTE and x.get('isSpotTradingAllowed') is not False]

def spot_tickers():
    raw=get_json('/api/v3/ticker/24hr',{'type':'FULL'}) or []
    return {str(x.get('symbol')):x for x in raw if isinstance(x,dict)}

def klines(symbol):
    raw=get_json('/api/v3/klines',{'symbol':symbol,'interval':'1h','limit':25}) or []
    now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
    rows=[]
    for r in raw:
        try:
            if int(r[6]) >= now_ms:
                continue
            if len(r)>=8: rows.append({'open_time':int(r[0]),'close_time':int(r[6]),'open':num(r[1]),'high':num(r[2]),'low':num(r[3]),'close':num(r[4]),'volume':num(r[5]),'quote_volume':num(r[7])})
        except (TypeError,ValueError,IndexError):
            continue
    if len(rows)<8:return None
    prior=[x['quote_volume'] for x in rows[:-1] if x['quote_volume']>0];last=rows[-1]
    baseline=sum(x['quote_volume'] for x in prior[-6:])/max(1,len(prior[-6:]));median=sorted(prior)[len(prior)//2] if prior else 0
    base=rows[-7]['close'] or last['close'];high=max(x['high'] for x in rows[-7:]);low=min(x['low'] for x in rows[-7:])
    return {'last_1h_quote_volume':last['quote_volume'],'avg_prior_6h_quote_volume':baseline,'volume_acceleration':round(last['quote_volume']/baseline,3) if baseline else 0,'volume_vs_24h_median':round(last['quote_volume']/median,3) if median else 0,'price_change_6h_pct':round((last['close']-base)/base*100,3) if base else 0,'range_6h_pct':round((high-low)/last['close']*100,3) if last['close'] else 0,'close_position_6h':round((last['close']-low)/(high-low),3) if high>low else .5,'breakout_distance_pct':round((high-last['close'])/last['close']*100,3) if last['close'] else 0}

def derivatives(symbol):
    prem=get_json('/fapi/v1/premiumIndex',{'symbol':symbol},True);hist=get_json('/futures/data/openInterestHist',{'symbol':symbol,'period':'1h','limit':4},True);r={}
    if isinstance(prem,dict):r['funding_rate']=num(prem.get('lastFundingRate'));r['mark_price']=num(prem.get('markPrice'))
    if isinstance(hist,list) and len(hist)>=2:
        old=num(hist[0].get('sumOpenInterestValue') or hist[0].get('sumOpenInterest'));new=num(hist[-1].get('sumOpenInterestValue') or hist[-1].get('sumOpenInterest'));r['oi_change_3h_pct']=round((new-old)/old*100,3) if old else 0
    return r or None

def score(row):
    vol=row.get('volume_acceleration',1);rel=row.get('relative_strength_24h',0);rng=row.get('range_6h_pct',0);oi=row.get('oi_change_3h_pct',0);fund=abs(row.get('funding_rate',0))*10000;dist=row.get('breakout_distance_pct',99);move=abs(row.get('price_change_percent',0));
    s=min(30,max(0,(vol-1)*12))+min(18,max(0,rel*1.2))+min(12,max(0,(row.get('volume_vs_24h_median',1)-1)*5))+min(12,max(0,oi*1.5))+min(8,max(0,fund-2))+min(10,max(0,6-rng))+min(10,max(0,5-dist))
    if move>12:s-=18
    elif move>8:s-=10
    elif move>5:s-=5
    if row.get('close_position_6h',0)<.35 and rel>0:s-=4
    return round(max(0,min(100,s)),2)

def classify(x,previous):
    move=abs(num(x.get('price_change_percent')));vol=num(x.get('volume_acceleration'));med=num(x.get('volume_vs_24h_median'));oi=num(x.get('oi_change_3h_pct'));dist=num(x.get('breakout_distance_pct'));score_v=num(x.get('discovery_score'));close=num(x.get('close_position_6h'));prev=previous.get(x.get('symbol'),{}) if isinstance(previous,dict) else {}
    # Exhaustion/late is deliberately conservative: strong move + extension beats a high score.
    if move>=12 or (move>=8 and dist<=1 and vol>=2.5):state='EXHAUSTED'
    elif move>=6 or (dist<=1 and vol>=2):state='LATE'
    elif score_v>=72 and vol>=2 and med>=1.5 and (oi>=2 or dist<=3):state='CONFIRMED'
    elif score_v>=55 and vol>=1.5 and med>=1.2 and (oi>=1 or dist<=5):state='DEVELOPING'
    elif score_v>=45 and (vol>=1.25 or med>=1.2) and move<=5:state='EARLY'
    else:state='WATCH'
    history=list(prev.get('states') or [])[-5:];history.append(state)
    return state,history

def main():
    universe=exchange_symbols();tickers=spot_tickers();rows=[]
    for u in universe:
        t=tickers.get(u['symbol']);
        if not t:continue
        pct=num(t.get('priceChangePercent'));qv=num(t.get('quoteVolume'));last=num(t.get('lastPrice'));hi=num(t.get('highPrice'));lo=num(t.get('lowPrice'))
        if qv<=0 or last<=0:continue
        rows.append({'symbol':u['asset'],'symbol_usdt':u['symbol'],'last_price':last,'price_change_percent':pct,'quote_volume_usdt':qv,'intraday_range_percent':round((hi-lo)/last*100,3) if last else 0})
    avg=sum(x['price_change_percent'] for x in rows)/max(1,len(rows))
    for x in rows:x['relative_strength_24h']=round(x['price_change_percent']-avg,3)
    rows.sort(key=lambda x:(abs(x['relative_strength_24h']),math.log10(max(1,x['quote_volume_usdt']))),reverse=True)
    enrich=rows[:ENRICH_N]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(klines,x['symbol_usdt']):x for x in enrich}
        for f in as_completed(futs):
            try:
                k=f.result()
                if k:futs[f].update(k)
            except Exception:pass
    for x in enrich:x['discovery_score']=score(x)
    enrich.sort(key=lambda x:x['discovery_score'],reverse=True);deriv=enrich[:DERIV_N]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs={ex.submit(derivatives,x['symbol_usdt']):x for x in deriv}
        for f in as_completed(futs):
            try:
                d=f.result()
                if d:futs[f].update(d)
            except Exception:pass
    for x in deriv:x['discovery_score']=score(x)
    enrich.sort(key=lambda x:x['discovery_score'],reverse=True)
    old=load(STATE).get('symbols') or {};early=[]
    for x in enrich:
        state,hist=classify(x,old);x['flow_state']=state;x['state_history']=hist;x['early_mover']=state in {'EARLY','DEVELOPING'};x['confirmation_required']=state in {'EARLY','DEVELOPING'};x['evidence']=[k for k in ('volume_acceleration','volume_vs_24h_median','relative_strength_24h','oi_change_3h_pct','funding_rate','breakout_distance_pct') if k in x]
        if x['early_mover'] and x['discovery_score']>=45:early.append(x)
    payload={'version':'2.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'OK','universe':{'spot_usdt_symbols':len(rows),'exchange_info_symbols':len(universe),'fully_enriched':len(enrich),'derivatives_enriched':len(deriv)},'market_breadth':{'average_24h_change':round(avg,4)},'early_movers':early[:40],'top_flow_candidates':enrich[:60],'all_live_symbols':[x['symbol'] for x in rows],'state_definitions':{'EARLY':'participation is abnormal but price is not yet extended; hypothesis only','DEVELOPING':'multiple independent participation/structure signals are strengthening','CONFIRMED':'strong participation plus structure/derivatives evidence; still conditional','LATE':'move is already advanced or breakout is too close to current price','EXHAUSTED':'parabolic/overextended conditions; do not chase','WATCH':'insufficient evidence'},'method':['Full Binance USDT spot universe from exchangeInfo','24h ticker breadth for every live symbol','1h volume acceleration and short-term structure for top 120 unusual/liquid assets','funding and open-interest context for top 80','relative strength versus market average','extension penalty to reduce late pump chasing'],'policy':['Discovery is not a prediction guarantee.','Only EARLY/DEVELOPING candidates may enter the early-discovery lane.','CONFIRMED still requires a verified trigger/invalidation before directional publishing.','LATE and EXHAUSTED candidates are excluded from early-mover publishing.','Order flow/funding/OI are context, not proof of whale activity or future direction.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8');STATE.write_text(json.dumps({'version':'2.0','updated_at':payload['generated_at'],'symbols':{x['symbol']: {'state':x['flow_state'],'states':x.get('state_history',[]),'discovery_score':x.get('discovery_score',0)} for x in enrich}},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','spot_usdt_universe':len(rows),'fully_enriched':len(enrich),'derivatives_enriched':len(deriv),'early_movers':len(early),'states':{s:sum(1 for x in enrich if x.get('flow_state')==s) for s in ('EARLY','DEVELOPING','CONFIRMED','LATE','EXHAUSTED','WATCH')},'top_candidate':early[0] if early else None},indent=2))
if __name__=='__main__':main()
