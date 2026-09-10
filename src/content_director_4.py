"""Creator 7.0 evidence-first content director.

The director compares fresh news, technical/momentum anomalies, capital rotation,
research candidates and accountability lanes. News is a candidate, never an
automatic override. All scores are normalized to 0-100.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json';NEWS=ROOT/'data/live/news_snapshot.json';PREFLIGHT=ROOT/'data/live/editorial_preflight.json';FEEDBACK=ROOT/'data/intelligence/performance_feedback.json';FLOW=ROOT/'data/live/capital_flow_intelligence.json';RESEARCH=ROOT/'data/live/original_research.json';OUT=ROOT/'data/live/content_director_brief.json'
FORMAT={'breaking_news':'BREAKING NEWS + MARKET IMPACT','news_and_macro':'NEWS + CHART','top_gainers':'MOMENTUM + FOLLOW-THROUGH','top_losers':'BREAKOUT / FAKEOUT','high_volatility':'VOLATILITY + TEST','volume_leaders':'DATA SURPRISE','new_listings':'NEW LISTING WATCH','technical_setup':'TRADINGVIEW CHART CHALLENGE','comparison':'COIN VS COIN','education':'ONE CHART / ONE LESSON','creator_signal_outcome':'CALL OUTCOME / ACCOUNTABILITY','follow_up':'FOLLOW-UP / UPDATE','capital_flow_long':'CAPITAL FLOW LONG SETUP','capital_flow_short':'CAPITAL FLOW SHORT SETUP','watchlist':'MARKET RADAR'}
NARRATIVE={'breaking_news':'event_context_impact','news_and_macro':'event_context_impact','top_gainers':'momentum_question','top_losers':'contrarian_risk','high_volatility':'volatility_then_test','volume_leaders':'data_vs_price','new_listings':'price_discovery','technical_setup':'level_confirmation','comparison':'compare_tradeoffs','education':'one_chart_one_lesson','creator_signal_outcome':'call_result_next_test','follow_up':'thesis_update','capital_flow_long':'capital_rotation','capital_flow_short':'capital_rotation','watchlist':'what_to_watch'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def rows(v):return v if isinstance(v,list) else []
def n(v,d=0):
    try:return float(v)
    except Exception:return d
def clamp(v):return round(max(0,min(100,n(v))),2)
def sym(v):
    s=str(v or '').upper().replace('$','').replace('BINANCE:','').strip();return s[:-4] if s.endswith('USDT') else s
def valid(s):return bool(re.fullmatch(r'[A-Z][A-Z0-9]{0,14}',str(s or '')))
def research_map(r):return {sym(x.get('symbol')):x for x in rows(r.get('potential_gems'))+rows(r.get('potential_risks')) if isinstance(x,dict) and x.get('symbol')}
def market_items(m):
    out=[]
    for g in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        out.extend(x for x in rows(m.get(g)) if isinstance(x,dict) and x.get('symbol'))
    return out
def market_score(x,r=None):
    move=abs(n(x.get('price_change_percent')));rng=n(x.get('intraday_range_percent'));signal=n(x.get('content_signal_score'));vol=n(x.get('quote_volume_usdt') or x.get('quote_volume'))
    base=clamp(move*2.8+rng*.7+signal*.32+min(20,vol/1e8*20))
    if r:
        info=clamp(r.get('information_advantage_score'));ev=clamp(r.get('evidence_score'));under=clamp(r.get('undercoverage_score'));risk=clamp(r.get('risk_red_flag_score'));missing=len(rows(r.get('missing_evidence')))
        base=clamp(base*.6+(info*.2+ev*.12+under*.08)-min(15,missing*2))
    return base
def news_score(a):
    raw=clamp(a.get('news_score'));title=str(a.get('title') or '').lower()
    if any(k in title for k in ('hack','exploit','etf','sec','approval','listing','launch','upgrade','regulation')):raw=clamp(raw+8)
    return raw
def flow_score(a):
    m=a.get('multitimeframe') or {};conf=clamp(m.get('confidence') or a.get('confidence'));flow=clamp(m.get('flow_proxy_score'),50);rs=abs(n(a.get('relative_strength_to_btc')));setup=a.get('trade_setup') or {};complete=all(setup.get(k) is not None for k in ('trigger','invalidation'))
    return clamp(conf*.45+flow*.3+clamp(50+rs*5)*.25+(8 if complete else -8))
def main():
    market,news,pre,feedback,flow,research=load(MARKET),load(NEWS),load(PREFLIGHT),load(FEEDBACK),load(FLOW),load(RESEARCH);selected=pre.get('selected_opportunity') or {};rmap=research_map(research);stories=[]
    for x in market_items(market):
        s=sym(x.get('symbol'));cat='top_gainers' if n(x.get('price_change_percent'))>0 else 'top_losers';score=market_score(x,rmap.get(s));stories.append({'type':'market','category':cat,'symbol':s,'score':score,'reason':'live market anomaly with supplied evidence','has_chart':bool(x.get('candles_1h')),'data_quality':'OK' if x.get('candles_1h') else 'LIMITED'})
    for a in rows(news.get('articles')):
        title=str(a.get('title') or '').strip();
        if not title:continue
        age=None
        try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(str(a.get('published_at','')).replace('Z','+00:00'))).total_seconds()/60
        except Exception:pass
        if age is not None and (age < -10 or age > 180):continue
        syms=[sym(x) for x in rows(a.get('symbols')) if valid(sym(x))]
        if not syms:continue
        for s in syms[:2]:stories.append({'type':'news','category':'breaking_news' if news_score(a)>=70 else 'news_and_macro','symbol':s,'score':news_score(a),'title':title[:240],'source':str(a.get('source') or ''),'url':str(a.get('url') or ''),'published_at':str(a.get('published_at') or '')})
    for a in rows(flow.get('top_conditional_setups')):
        if not isinstance(a,dict):continue
        s=sym(a.get('symbol'));setup=a.get('trade_setup') or {};side=str(setup.get('side') or 'WAIT').upper();conf=n((a.get('multitimeframe') or {}).get('confidence') or a.get('confidence'))
        if valid(s) and side in {'LONG','SHORT'} and conf>=65:stories.append({'type':'flow','category':'capital_flow_long' if side=='LONG' else 'capital_flow_short','symbol':s,'score':flow_score(a),'reason':'multi-timeframe rotation setup','trade_setup':setup,'flow_confidence':conf,'relative_strength_to_btc':a.get('relative_strength_to_btc'),'flow_proxy_score':(a.get('multitimeframe') or {}).get('flow_proxy_score'),'flow_notes':a.get('flow_notes') or []})
    # Research-only gems become editorial candidates only when evidence is usable.
    for s,r in rmap.items():
        info=clamp(r.get('information_advantage_score'));ev=clamp(r.get('evidence_score'));missing=len(rows(r.get('missing_evidence')));liq=clamp(r.get('liquidity_score'));risk=clamp(r.get('risk_red_flag_score'));score=clamp(.35*info+.25*ev+.2*liq+.2*(100-risk)-min(20,missing*3))
        if score>=68:stories.append({'type':'research','category':'watchlist','symbol':s,'score':score,'reason':'asset-specific research anomaly with evidence','research':r,'data_quality':'RESEARCH'})
    # Existing authoritative selection is only a hint. Re-rank it against the live lanes.
    for st in stories:
        if st['symbol']==sym(selected.get('symbol')) and selected.get('category'):st['score']=clamp(st['score']+4);st['authoritative_hint']=True
    # Small learning bonus; never enough to override weak evidence.
    prefs=feedback.get('learned_preferences') or {}
    preferred=str((prefs.get('format') or {}).get('prefer') or '').lower()
    for st in stories:
        if preferred and FORMAT.get(st.get('category',''),'').lower()==preferred:st['score']=clamp(st['score']+4)
    stories.sort(key=lambda x:x['score'],reverse=True);best=stories[0] if stories else None
    publish=bool(best and best['score']>=72 and best.get('symbol'))
    if not best:reason='no_candidates'
    elif not publish:reason='best_candidate_below_quality_threshold'
    else:reason='cross_lane_best_opportunity'
    out_selected=None
    if publish:
        out_selected={'category':best['category'],'symbol':best['symbol']+'USDT' if best['symbol'] not in {'XAUUSD','XAGUSD'} else best['symbol'],'reason':best['reason'],'score':best['score'],'lane':best['type']}
        for k in ('title','source','url','published_at','trade_setup','flow_confidence','relative_strength_to_btc','flow_proxy_score','flow_notes'):
            if k in best:out_selected[k]=best[k]
    # News symbol/chart coherence: no arbitrary BTC fallback.
    chart=[]
    if out_selected and best.get('type') in {'market','flow'} and valid(best.get('symbol')):chart=[best['symbol']]
    if out_selected and best.get('type')=='news' and best.get('symbol'):chart=[best['symbol']]
    visual_type='candlestick_chart' if chart else ('news_timeline' if best and best.get('type')=='news' else 'none')
    brief={'generated_at':datetime.now(timezone.utc).isoformat(),'director_version':'7.0','run_ai':publish,'reason':reason,'primary_story':{'symbol':out_selected.get('symbol','') if out_selected else '','lane':best.get('category') if best else None,'score':best.get('score') if best else 0,'chart_symbols':chart} if best else {},'authoritative_selection':out_selected,'ranked_stories':stories[:40],'lane_scores':{'news':max([x['score'] for x in stories if x['type']=='news'],default=0),'flow':max([x['score'] for x in stories if x['type']=='flow'],default=0),'market':max([x['score'] for x in stories if x['type']=='market'],default=0),'research':max([x['score'] for x in stories if x['type']=='research'],default=0)},'recommended_format':FORMAT.get(best.get('category'),'MARKET RADAR') if best else 'WAIT','narrative_engine':NARRATIVE.get(best.get('category'),'what_to_watch') if best else 'what_to_watch','visual_plan':{'provider':'TradingView' if chart else 'none','layout':'single_panel','symbols':chart,'timeframe':'1H','custom_overlays':False,'type':visual_type,'required':bool(out_selected and best.get('type') in {'market','flow'}),'reason':'Chart must prove the selected market/flow thesis; news-only stories use a news visual.'},'interaction_plan':{'primary_goal':'specific conversation','question_rule':'exactly one story-specific question','avoid':['What do you think?','Thoughts?','Bullish, bearish, or wait?']},'writing_contract':['Choose the highest-information-gain lane, not automatically the freshest news.','Every selected asset must have an explicit reason, evidence and why-now.','News does not imply BTC; never manufacture an asset link.','Capital-flow LONG/SHORT content is conditional and requires trigger plus invalidation.','Research-only opportunities with material missing evidence should be WAIT/watchlist, not buy calls.','All scores are normalized to 0-100.','Never invent targets, stops, prices, sources or outcomes.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8');pre['content_director_4']=brief
    if out_selected:pre['selected_opportunity']=out_selected
    else:pre['selected_opportunity']=None
    PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'7.0','publish':publish,'reason':reason,'selected':out_selected,'lane_scores':brief['lane_scores']},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
