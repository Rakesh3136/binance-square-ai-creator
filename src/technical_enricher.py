import json, re, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
AUTHORITATIVE=ROOT/'data/live/authoritative_opportunity.json'
MARKET=ROOT/'data/live/market_snapshot.json'
REPORTS=ROOT/'data/reports'
TECH_LANES={'technical_setup','high_volatility','top_gainers','top_losers','creator_signal_outcome'}
BINANCE_BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com']


def load(p, default=None):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,type(default if default is not None else {})) else (default if default is not None else {})
    except Exception:return default if default is not None else {}


def find_item(market,symbol):
    target=str(symbol or '').upper().replace('USDT','')+'USDT'
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get('symbol','')).upper()==target:return x
    return None


def fetch_fresh_candles(symbol, limit=24):
    query=urllib.parse.urlencode({'symbol':symbol,'interval':'1h','limit':limit})
    last_error=None
    for base in BINANCE_BASES:
        try:
            req=urllib.request.Request(base+'/api/v3/klines?'+query,headers={'User-Agent':'binance-square-ai-creator/1.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r:
                raw=json.loads(r.read().decode('utf-8'))
            out=[]
            for row in raw:
                if len(row)>=6:
                    out.append({'open_time':int(row[0]),'open':float(row[1]),'high':float(row[2]),'low':float(row[3]),'close':float(row[4]),'volume':float(row[5])})
            if out:return out
        except Exception as exc:last_error=exc
    raise RuntimeError(f'fresh 1H candles unavailable: {last_error}')


def fmt(x): return f"{x:.8g}"


def main():
    frozen=load(AUTHORITATIVE,{})
    pre=load(PREFLIGHT,{})
    selected=frozen or (pre.get('selected_opportunity') or {})
    symbol=str(selected.get('symbol') or '').upper().replace('USDT','')
    category=str(selected.get('category') or '').lower()
    if category not in TECH_LANES or not symbol:
        print(json.dumps({'status':'SKIP','reason':'non-chart editorial lane'})); return
    market=load(MARKET,{})
    item=find_item(market,symbol)
    candles=(item or {}).get('candles_1h') or []
    # Never rely on stale/missing scanner candles for the authoritative asset.
    if len(candles)<6:
        candles=fetch_fresh_candles(symbol+'USDT')
        if item is None:item={'symbol':symbol+'USDT'}
        item['candles_1h']=candles
        # Keep the fresh candles available to the chart renderer in this run.
        for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
            for x in market.get(group) or []:
                if isinstance(x,dict) and str(x.get('symbol','')).upper()==symbol+'USDT':
                    x['candles_1h']=candles
    if len(candles)<6:
        raise SystemExit('insufficient fresh 1H candles for authoritative asset')
    highs=[float(c['high']) for c in candles[-12:]]
    lows=[float(c['low']) for c in candles[-12:]]
    last=float((item or {}).get('last_price') or candles[-1].get('close') or 0)
    support=min(lows); resistance=max(highs); span=max(resistance-support,0)
    target=resistance+span*0.5 if last<resistance else resistance+span
    invalidation=support
    reports=sorted(REPORTS.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:raise SystemExit('no draft')
    path=reports[0]; data=load(path,{})
    draft=data.get('draft') or {}; text=str(draft.get('post') or draft.get('text') or '').strip()
    if not text:raise SystemExit('empty draft')
    level_line=f"📊 Chart levels: support ${fmt(support)} • resistance ${fmt(resistance)} • target ${fmt(target)} • invalidation below ${fmt(invalidation)}."
    if 'Chart levels:' not in text:
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        question=lines.pop() if lines and '?' in lines[-1] else ''
        body='\n'.join(lines)
        enriched=(body+'\n'+level_line+'\nLevels are chart-derived scenarios, not guarantees.\n'+question).strip()
        draft['post']=enriched[:740]; draft['text']=draft['post']
    draft['visual_requested']=True; draft['visual_type']='tradingview_chart'
    data['draft']=draft
    data.setdefault('research',{})['chart_levels']={'support':support,'resistance':resistance,'target':target,'invalidation':invalidation,'method':'recent_12_1h_candles'}
    data.setdefault('visual_plan',{}).update({'use_visual':True,'type':'tradingview_chart','title':f'{symbol} 1H chart — support, resistance and measured target','symbol':symbol})
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    MARKET.write_text(json.dumps(market,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'ENRICHED','symbol':symbol,'support':support,'resistance':resistance,'target':target,'invalidation':invalidation,'visual_required':True,'candles':len(candles)}))

if __name__=='__main__': main()
