"""Bridge full-universe flow candidates into the existing Creator 6.5 ranker.

Keeps the mature ranker intact while expanding its candidate universe beyond
its legacy top-list slices. This file never invents symbols or prices: it only
copies verified candidates produced by full_universe_flow_scanner.py.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FLOW=ROOT/'data/live/full_universe_flow.json'
MARKET=ROOT/'data/live/market_snapshot.json'
BRIEF=ROOT/'data/live/content_director_brief.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}

def sym(s):return str(s or '').upper().replace('$','').replace('USDT','').strip()

def main():
    flow=load(FLOW);market=load(MARKET);brief=load(BRIEF)
    candidates=flow.get('early_movers') or []
    if not candidates:
        print(json.dumps({'status':'NO_FLOW_CANDIDATES','injected':0}));return
    existing={sym(x.get('symbol')) for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market') for x in (market.get(group) or []) if isinstance(x,dict)}
    injected=[]
    signals=market.setdefault('top_content_signals',[])
    for c in candidates[:40]:
        s=sym(c.get('symbol_usdt') or c.get('symbol'))
        if not s or s in existing:continue
        row={'symbol':s+'USDT','price_change_percent':c.get('price_change_percent',0),'last_price':c.get('last_price',0),'quote_volume_usdt':c.get('quote_volume_usdt',0),'intraday_range_percent':c.get('intraday_range_percent',0),'content_signal_score':c.get('discovery_score',0),'candles_1h':[],'full_universe_flow':True,'early_mover':True,'confirmation_required':True,'flow_state':c.get('flow_state'),'volume_acceleration':c.get('volume_acceleration'),'volume_vs_24h_median':c.get('volume_vs_24h_median'),'relative_strength_24h':c.get('relative_strength_24h'),'oi_change_3h_pct':c.get('oi_change_3h_pct'),'funding_rate':c.get('funding_rate'),'breakout_distance_pct':c.get('breakout_distance_pct'),'discovery_score':c.get('discovery_score'),'evidence':c.get('evidence') or []}
        signals.append(row);existing.add(s);injected.append(s)
    # Give the ranker a complete live-symbol authority without replacing its legacy lists.
    market['full_universe_symbol_count']=int((flow.get('universe') or {}).get('spot_usdt_symbols') or len(flow.get('all_live_symbols') or []))
    market['full_universe_symbols']=flow.get('all_live_symbols') or []
    market['full_universe_flow_candidates']=candidates[:40]
    MARKET.write_text(json.dumps(market,indent=2,ensure_ascii=False),encoding='utf-8')
    # Also expose the strongest flow candidates to the content director as explicit stories.
    stories=brief.setdefault('ranked_stories',[])
    known={(sym(x.get('symbol')),str(x.get('lane') or x.get('category') or '')) for x in stories if isinstance(x,dict)}
    for c in candidates[:20]:
        s=sym(c.get('symbol_usdt') or c.get('symbol'));lane='next_gainer_candidate' if float(c.get('price_change_percent') or 0)>0 else 'next_loser_candidate'
        key=(s,lane)
        if not s or key in known:continue
        stories.append({'symbol':s,'symbols':[s],'category':lane,'lane':lane,'score':float(c.get('discovery_score') or 0),'ranker_score':float(c.get('discovery_score') or 0),'price_change_percent':float(c.get('price_change_percent') or 0),'quote_volume_usdt':float(c.get('quote_volume_usdt') or 0),'intraday_range_percent':float(c.get('intraday_range_percent') or 0),'content_signal_score':float(c.get('discovery_score') or 0),'early_mover':True,'confirmation_required':True,'full_universe_flow':True,'flow_state':c.get('flow_state'),'volume_acceleration':c.get('volume_acceleration'),'volume_vs_24h_median':c.get('volume_vs_24h_median'),'relative_strength_24h':c.get('relative_strength_24h'),'oi_change_3h_pct':c.get('oi_change_3h_pct'),'funding_rate':c.get('funding_rate'),'breakout_distance_pct':c.get('breakout_distance_pct'),'evidence':c.get('evidence') or [],'reason':'Full-universe flow scan found unusual participation before treating the asset as a confirmed move.'});known.add(key)
    BRIEF.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','universe_size':market['full_universe_symbol_count'],'flow_candidates':len(candidates),'injected_into_market':len(injected),'brief_candidates':len(stories)},indent=2))

if __name__=='__main__':main()
