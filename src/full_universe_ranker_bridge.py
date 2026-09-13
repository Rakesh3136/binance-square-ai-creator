"""Bridge verified EARLY/DEVELOPING full-universe flow candidates into Creator 6.5."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FLOW=ROOT/'data/live/full_universe_flow.json';MARKET=ROOT/'data/live/market_snapshot.json';BRIEF=ROOT/'data/live/content_director_brief.json'
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def sym(s):return str(s or '').upper().replace('$','').replace('USDT','').strip()
def main():
    flow=load(FLOW);market=load(MARKET);brief=load(BRIEF);allc=flow.get('early_movers') or []
    candidates=[c for c in allc if str(c.get('flow_state','')).upper() in {'EARLY','DEVELOPING'}]
    existing={sym(x.get('symbol')) for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market') for x in (market.get(group) or []) if isinstance(x,dict)};injected=[];signals=market.setdefault('top_content_signals',[])
    for c in candidates[:40]:
        s=sym(c.get('symbol_usdt') or c.get('symbol'))
        if not s or s in existing:continue
        signals.append({'symbol':s+'USDT','price_change_percent':c.get('price_change_percent',0),'last_price':c.get('last_price',0),'quote_volume_usdt':c.get('quote_volume_usdt',0),'intraday_range_percent':c.get('intraday_range_percent',0),'content_signal_score':c.get('discovery_score',0),'candles_1h':[],'full_universe_flow':True,'early_mover':True,'confirmation_required':True,'flow_state':c.get('flow_state'),'state_history':c.get('state_history') or [],'volume_acceleration':c.get('volume_acceleration'),'volume_vs_24h_median':c.get('volume_vs_24h_median'),'relative_strength_24h':c.get('relative_strength_24h'),'oi_change_3h_pct':c.get('oi_change_3h_pct'),'funding_rate':c.get('funding_rate'),'breakout_distance_pct':c.get('breakout_distance_pct'),'discovery_score':c.get('discovery_score'),'evidence':c.get('evidence') or []});existing.add(s);injected.append(s)
    market['full_universe_symbol_count']=int((flow.get('universe') or {}).get('spot_usdt_symbols') or len(flow.get('all_live_symbols') or []));market['full_universe_symbols']=flow.get('all_live_symbols') or [];market['full_universe_flow_candidates']=candidates[:40];MARKET.write_text(json.dumps(market,indent=2,ensure_ascii=False),encoding='utf-8')
    stories=brief.setdefault('ranked_stories',[]);known={(sym(x.get('symbol')),str(x.get('lane') or x.get('category') or '')) for x in stories if isinstance(x,dict)}
    for c in candidates[:20]:
        s=sym(c.get('symbol_usdt') or c.get('symbol'));lane='next_gainer_candidate' if float(c.get('price_change_percent') or 0)>0 else 'next_loser_candidate';key=(s,lane)
        if not s or key in known:continue
        stories.append({'symbol':s,'symbols':[s],'category':lane,'lane':lane,'score':float(c.get('discovery_score') or 0),'ranker_score':float(c.get('discovery_score') or 0),'price_change_percent':float(c.get('price_change_percent') or 0),'quote_volume_usdt':float(c.get('quote_volume_usdt') or 0),'intraday_range_percent':float(c.get('intraday_range_percent') or 0),'content_signal_score':float(c.get('discovery_score') or 0),'early_mover':True,'confirmation_required':True,'full_universe_flow':True,'flow_state':c.get('flow_state'),'state_history':c.get('state_history') or [],'volume_acceleration':c.get('volume_acceleration'),'volume_vs_24h_median':c.get('volume_vs_24h_median'),'relative_strength_24h':c.get('relative_strength_24h'),'oi_change_3h_pct':c.get('oi_change_3h_pct'),'funding_rate':c.get('funding_rate'),'breakout_distance_pct':c.get('breakout_distance_pct'),'evidence':c.get('evidence') or [],'reason':'Full-universe scan found abnormal participation while the move is still EARLY/DEVELOPING; confirmation is required before a directional claim.'});known.add(key)
    BRIEF.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','universe_size':market['full_universe_symbol_count'],'raw_flow_candidates':len(allc),'eligible_early_developing':len(candidates),'injected_into_market':len(injected),'brief_candidates':len(stories)},indent=2))
if __name__=='__main__':main()
