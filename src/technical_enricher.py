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


def fetch_fresh_candles(symbol, limit=48):
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
    if len(candles)<12:
        candles=fetch_fresh_candles(symbol+'USDT')
        if item is None:item={'symbol':symbol+'USDT'}
        item['candles_1h']=candles
        for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
            for x in market.get(group) or []:
                if isinstance(x,dict) and str(x.get('symbol','')).upper()==symbol+'USDT':
                    x['candles_1h']=candles
    if len(candles)<12:
        raise SystemExit('insufficient fresh 1H candles for authoritative asset')

    window=candles[-24:]
    highs=[float(c['high']) for c in window]
    lows=[float(c['low']) for c in window]
    closes=[float(c['close']) for c in window]
    last=float((item or {}).get('last_price') or closes[-1] or 0)
    support=min(lows)
    resistance=max(highs)
    span=max(resistance-support,0.0)

    # Direction is evidence-based: compare the latest close with the first close
    # in the 24-hour window, with the live market move as a secondary signal.
    try:
        market_move=float((item or {}).get('price_change_percent') or 0)
    except Exception:
        market_move=0.0
    window_move=((closes[-1]/closes[0])-1)*100 if closes[0] else market_move
    direction='LONG_BIAS' if (window_move if abs(window_move)>0.01 else market_move) >= 0 else 'SHORT_BIAS'

    if direction=='LONG_BIAS':
        tp1=resistance + span*0.25
        target=resistance + span*0.50
        invalidation=support
        sl_label='SL / invalidation'
    else:
        tp1=max(0.0, support - span*0.25)
        target=max(0.0, support - span*0.50)
        invalidation=resistance
        sl_label='SL / invalidation'

    reports=sorted(REPORTS.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:raise SystemExit('no draft')
    path=reports[0]
    data=load(path,{})
    draft=data.get('draft') or {}
    text=str(draft.get('post') or draft.get('text') or '').strip()
    if not text:raise SystemExit('empty draft')

    level_line=(
        f"📊 {symbol} 1H: price ${fmt(last)} • support ${fmt(support)} • resistance ${fmt(resistance)} • "
        f"TP1 ${fmt(tp1)} • target ${fmt(target)} • {sl_label} ${fmt(invalidation)} ({direction.replace('_',' ').lower()})."
    )
    if '📊 ' + symbol + ' 1H:' not in text:
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        question=lines.pop() if lines and '?' in lines[-1] else ''
        body='\n'.join(lines)
        enriched=(body+'\n'+level_line+'\nLevels are chart-derived scenarios, not guarantees.\n'+question).strip()
        draft['post']=enriched[:890]
        draft['text']=draft['post']

    draft['visual_requested']=True
    draft['visual_type']='tradingview_chart'
    draft['technical_levels']={
        'current_price':last,'support':support,'resistance':resistance,
        'tp1':tp1,'target':target,'invalidation':invalidation,'direction':direction,
        'timeframe':'1H','method':'fresh_24_1h_candles'
    }
    data['draft']=draft
    data.setdefault('research',{})['chart_levels']={
        'current_price':last,'support':support,'resistance':resistance,
        'tp1':tp1,'target':target,'invalidation':invalidation,'direction':direction,
        'method':'fresh_24_1h_candles'
    }
    data.setdefault('visual_plan',{}).update({
        'use_visual':True,'type':'tradingview_chart',
        'title':f'{symbol} 1H TradingView chart — support, resistance, TP1, target and SL',
        'symbol':symbol,
        'annotations':['current_price','support','resistance','tp1','target','invalidation']
    })
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    MARKET.write_text(json.dumps(market,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'ENRICHED','symbol':symbol,'direction':direction,'current_price':last,'support':support,'resistance':resistance,'tp1':tp1,'target':target,'invalidation':invalidation,'visual_required':True,'candles':len(candles)}))

if __name__=='__main__': main()
