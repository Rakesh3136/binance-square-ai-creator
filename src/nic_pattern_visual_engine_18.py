"""NIC 18 — evidence-bound market-pattern detector for chart visuals.

Detects only patterns supported by the fresh 1H candle set. It never invents a
pattern merely to make a chart look different. Output is a visual contract used
by the chart overlay.
"""
from __future__ import annotations
import json
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'
PREF=ROOT/'data/live/editorial_preflight.json'
REPORTS=ROOT/'data/reports'
OUT=ROOT/'data/live/nic_pattern_visual_engine_18.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def symbol_from(pre, reports):
    s=str((pre.get('selected_opportunity') or {}).get('symbol') or '').upper().replace('USDT','')
    if s:return s
    if reports:
        d=load(reports[0]).get('draft') or {}
        return str(d.get('symbol') or '').upper().replace('USDT','')
    return ''

def find_candles(market,symbol):
    target=symbol+'USDT'
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get('symbol','')).upper()==target:
                return x.get('candles_1h') or []
    return []

def regression_slope(values):
    n=len(values); mx=(n-1)/2; my=mean(values)
    den=sum((i-mx)**2 for i in range(n))
    return sum((i-mx)*(v-my) for i,v in enumerate(values))/den if den else 0.0

def main():
    pre=load(PREF); market=load(MARKET)
    reports=sorted(REPORTS.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    symbol=symbol_from(pre,reports)
    candles=find_candles(market,symbol)
    if len(candles)<20:
        OUT.write_text(json.dumps({'status':'SKIP','reason':'insufficient_1h_candles','symbol':symbol},indent=2),encoding='utf-8')
        print(json.dumps({'status':'SKIP','reason':'insufficient_1h_candles'})); return 0
    c=candles[-24:]
    closes=[float(x['close']) for x in c]; highs=[float(x['high']) for x in c]; lows=[float(x['low']) for x in c]
    prior=c[:-3]; recent=c[-3:]
    prior_high=max(float(x['high']) for x in prior); prior_low=min(float(x['low']) for x in prior)
    last=closes[-1]; prev=closes[-2]
    span=max(prior_high-prior_low,0.0); baseline=max(abs(mean(closes)),1e-12)
    patterns=[]
    # Breakout/breakdown requires a close outside the prior range, not merely a wick.
    if span>0 and last>prior_high and last>prev:
        patterns.append({'type':'BREAKOUT_UP','confidence':'evidence_bound','level':prior_high,'label':'BREAKOUT'})
    elif span>0 and last<prior_low and last<prev:
        patterns.append({'type':'BREAKDOWN','confidence':'evidence_bound','level':prior_low,'label':'BREAKDOWN'})
    # Range only when price remains inside a relatively stable prior range.
    range_width=span/baseline
    if not patterns and range_width < 0.08 and prior_low <= last <= prior_high:
        patterns.append({'type':'RANGE','confidence':'evidence_bound','support':prior_low,'resistance':prior_high,'label':'RANGE'})
    # Trend structure from normalized regression slope.
    slope=regression_slope(closes[-12:]); normalized=slope/baseline
    if abs(normalized)>0.001 and not any(p['type'] in {'BREAKOUT_UP','BREAKDOWN'} for p in patterns):
        patterns.append({'type':'UPTREND_STRUCTURE' if normalized>0 else 'DOWNTREND_STRUCTURE','confidence':'evidence_bound','label':'UPTREND' if normalized>0 else 'DOWNTREND'})
    if not patterns:
        patterns.append({'type':'STRUCTURE_NEUTRAL','confidence':'evidence_bound','label':'STRUCTURE'})
    result={'version':'18.0','status':'DETECTED','symbol':symbol,'timeframe':'1H','pattern':patterns[0],
            'levels':{'prior_high':prior_high,'prior_low':prior_low,'last_close':last},
            'candles_used':len(c)}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
