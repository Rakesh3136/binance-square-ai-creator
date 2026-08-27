import json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
MARKET=ROOT/'data/live/market_snapshot.json'
REPORTS=ROOT/'data/reports'
TECH_WORDS=re.compile(r'\b(breakout|fakeout|support|resistance|rsi|ema|fib|target|stop[- ]?loss|sl\b|tp\b|entry|setup|chart)\b',re.I)

def load(p, default=None):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,type(default if default is not None else {})) else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}

def find_item(market,symbol):
    target=str(symbol or '').upper().replace('USDT','')+'USDT'
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get('symbol','')).upper()==target:return x
    return None

def fmt(x): return f"{x:.8g}"

def main():
    pre=load(PREFLIGHT,{})
    selected=pre.get('selected_opportunity') or {}
    category=str(selected.get('category') or '').lower()
    if category not in {'technical_setup','high_volatility','top_gainers','top_losers','creator_signal_outcome'}:
        print(json.dumps({'status':'SKIP','reason':'non-technical editorial lane'})); return
    market=load(MARKET,{})
    item=find_item(market,selected.get('symbol'))
    if not item: print(json.dumps({'status':'SKIP','reason':'no matching live market item'})); return
    candles=item.get('candles_1h') or []
    if len(candles)<6: print(json.dumps({'status':'SKIP','reason':'insufficient 1H candles'})); return
    highs=[float(c['high']) for c in candles[-12:] if c.get('high') is not None]
    lows=[float(c['low']) for c in candles[-12:] if c.get('low') is not None]
    last=float(item.get('last_price') or candles[-1].get('close') or 0)
    support=min(lows); resistance=max(highs); span=max(resistance-support,0)
    target=resistance+span if last>=resistance else resistance+span*0.5
    invalidation=support
    symbol=str(item.get('symbol')).upper().replace('USDT','')
    report_files=sorted(REPORTS.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not report_files: print(json.dumps({'status':'SKIP','reason':'no draft'})); return
    path=report_files[0]; data=load(path,{})
    draft=data.get('draft') or {}; text=str(draft.get('post') or draft.get('text') or '').strip()
    if not text or (not TECH_WORDS.search(text) and category!='technical_setup'):
        print(json.dumps({'status':'SKIP','reason':'draft is not technical'})); return
    level_line=f"Levels: support ${fmt(support)} • resistance ${fmt(resistance)} • measured target ${fmt(target)} • invalidation < ${fmt(invalidation)}."
    if 'Levels: support' not in text:
        # Keep the creator's question as the final line so engagement checks remain valid.
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        question=lines.pop() if lines and '?' in lines[-1] else ''
        body='\n'.join(lines)
        enriched=(body+'\n'+level_line+'\n'+('Chart-derived, not guaranteed.' if question else '')+'\n'+question).strip()
        enriched=enriched[:740]
        draft['post']=enriched; draft['text']=enriched; data['draft']=draft
        data.setdefault('research',{})['chart_levels']={'support':support,'resistance':resistance,'target':target,'invalidation':invalidation,'method':'recent_12_candles'}
        data.setdefault('visual_plan',{})['use_visual']=True; data['visual_plan']['type']='candlestick_chart'
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps({'status':'ENRICHED','symbol':symbol,'support':support,'resistance':resistance,'target':target,'invalidation':invalidation}))
    else: print(json.dumps({'status':'SKIP','reason':'already enriched'}))

if __name__=='__main__': main()
