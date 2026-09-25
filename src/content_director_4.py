"""Creator 7.1 evidence-first, high-intent content director."""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json';NEWS=ROOT/'data/live/news_snapshot.json';PREFLIGHT=ROOT/'data/live/editorial_preflight.json';FEEDBACK=ROOT/'data/intelligence/performance_feedback.json';FLOW=ROOT/'data/live/capital_flow_intelligence.json';RESEARCH=ROOT/'data/live/original_research.json';RANKING=ROOT/'data/live/opportunity_ranking_6.json';OUT=ROOT/'data/live/content_director_brief.json'
FORMAT={'breaking_news':'CATALYST + MARKET IMPACT','news_and_macro':'CATALYST + CHART','top_gainers':'MOMENTUM EXPLAINER','top_losers':'BREAKDOWN / FAKEOUT ANALYSIS','high_volatility':'VOLATILITY + TEST','volume_leaders':'DATA SURPRISE','new_listings':'PRICE DISCOVERY WATCH','technical_setup':'TRADINGVIEW DECISION CHART','comparison':'COIN VS COIN','education':'ONE CHART / ONE LESSON','research_insight':'NEW RESEARCH / WHAT WE LEARNED','market_mechanism':'HOW THE MARKET MECHANISM WORKS','data_surprise':'DATA SURPRISE / WHY IT MATTERS','creator_signal_outcome':'CALL OUTCOME / ACCOUNTABILITY','follow_up':'FOLLOW-UP / UPDATE','capital_flow_long':'CAPITAL FLOW LONG THESIS','capital_flow_short':'CAPITAL FLOW SHORT THESIS','watchlist':'DEEP RESEARCH RADAR','next_gainer_candidate':'EARLY-MOVER CONFIRMATION WATCH','next_loser_candidate':'EARLY-MOVER BREAKDOWN WATCH'}
NARRATIVE={'breaking_news':'event_context_impact','news_and_macro':'event_context_impact','top_gainers':'momentum_mechanism','top_losers':'contrarian_risk','high_volatility':'volatility_then_test','volume_leaders':'data_vs_price','new_listings':'price_discovery','technical_setup':'level_confirmation','comparison':'compare_tradeoffs','education':'live_market_lesson','research_insight':'research_finding_explained','market_mechanism':'mechanism_explainer','data_surprise':'data_finding_explained','creator_signal_outcome':'call_result_next_test','follow_up':'thesis_update','capital_flow_long':'capital_rotation','capital_flow_short':'capital_rotation','watchlist':'deep_research_radar','next_gainer_candidate':'early_confirmation','next_loser_candidate':'early_breakdown'}
PRIMARY_RESEARCH={'watchlist','research_insight','market_mechanism','data_surprise','education','capital_flow_long','capital_flow_short','technical_setup','comparison','creator_signal_outcome','follow_up','news_and_macro','breaking_news'}
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
    base=min(86,clamp(move*1.9+rng*.5+signal*.24+min(15,vol/1e8*15)))
    if r:
        info=clamp(r.get('information_advantage_score'));ev=clamp(r.get('evidence_score'));under=clamp(r.get('undercoverage_score'));risk=clamp(r.get('risk_red_flag_score'));missing=len(rows(r.get('missing_evidence')))
        base=clamp(base*.55+info*.2+ev*.15+under*.1-min(18,missing*3))
    return base
def news_score(a):
    raw=clamp(a.get('news_score'));title=str(a.get('title') or '').lower()
    if any(k in title for k in ('hack','exploit','etf','sec','approval','listing','launch','upgrade','regulation')):raw=clamp(raw+8)
    return raw
def flow_score(a):
    m=a.get('multitimeframe') or {};conf=clamp(m.get('confidence') if m.get('confidence') is not None else a.get('confidence'));flow=clamp(m.get('flow_proxy_score') if m.get('flow_proxy_score') is not None else 50);rs=abs(n(a.get('relative_strength_to_btc')));setup=a.get('trade_setup') or {};complete=all(setup.get(k) is not None for k in ('trigger','invalidation'))
    return clamp(conf*.45+flow*.3+clamp(50+rs*5)*.25+(8 if complete else -8))
def research_score(r):
    info=clamp(r.get('information_advantage_score'));ev=clamp(r.get('evidence_score'));under=clamp(r.get('undercoverage_score'));liq=clamp(r.get('liquidity_score'));risk=clamp(r.get('risk_red_flag_score'));missing=len(rows(r.get('missing_evidence')))
    return clamp(info*.3+ev*.3+under*.2+liq*.1+(100-risk)*.1-min(20,missing*3))
def safe_reason(x,default='selected opportunity'):
    reason=x.get('reason')
    return str(reason) if reason else 'evidence-ranked opportunity; confirmation required'
def ranking_candidates(ranking):
    out=[]
    selected=ranking.get('selected')
    source=rows(ranking.get('top_candidates'))
    if isinstance(selected,dict):source=[selected]+source
    for x in source:
        if not isinstance(x,dict):continue
        s=sym(x.get('symbol')); cat=str(x.get('category') or x.get('lane') or 'market').lower();score=clamp(x.get('score',x.get('ranker_score',0)))
        if valid(s) and score>=62:
            y=dict(x);y.update({'type':'market','category':cat,'symbol':s,'score':score,'reason':safe_reason(x),'content_intent':x.get('content_intent') or 'investigate_confirm_invalidate','authoritative_ranking':True});out.append(y)
    return out
def main():
    market,news,pre,feedback,flow,research,ranking=load(MARKET),load(NEWS),load(PREFLIGHT),load(FEEDBACK),load(FLOW),load(RESEARCH),load(RANKING);selected=pre.get('selected_opportunity') or {};rmap=research_map(research);stories=ranking_candidates(ranking)
    for x in market_items(market):
        s=sym(x.get('symbol'));cat='top_gainers' if n(x.get('price_change_percent'))>0 else 'top_losers';score=market_score(x,rmap.get(s));stories.append({'type':'market','category':cat,'symbol':s,'score':score,'reason':'live market anomaly with supplied evidence','has_chart':bool(x.get('candles_1h')),'data_quality':'OK' if x.get('candles_1h') else 'LIMITED','content_intent':'investigate_confirm_invalidate'})
    for a in rows(news.get('articles')):
        title=str(a.get('title') or '').strip()
        if not title:continue
        age=None
        try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(str(a.get('published_at','')).replace('Z','+00:00'))).total_seconds()/60
        except Exception:pass
        if age is not None and (age < -10 or age > 180):continue
        syms=[sym(x) for x in rows(a.get('symbols')) if valid(sym(x))]
        for s in syms[:2]:stories.append({'type':'news','category':'breaking_news' if news_score(a)>=70 else 'news_and_macro','symbol':s,'score':news_score(a),'title':title[:240],'source':str(a.get('source') or ''),'url':str(a.get('url') or ''),'published_at':str(a.get('published_at') or ''),'content_intent':'event_to_market_impact','reason':'fresh news with identified asset'})
    for a in rows(flow.get('top_conditional_setups')):
        if not isinstance(a,dict):continue
        s=sym(a.get('symbol'));setup=a.get('trade_setup') or {};side=str(setup.get('side') or 'WAIT').upper();conf=n((a.get('multitimeframe') or {}).get('confidence') or a.get('confidence'))
        if valid(s) and side in {'LONG','SHORT'} and conf>=65:stories.append({'type':'flow','category':'capital_flow_long' if side=='LONG' else 'capital_flow_short','symbol':s,'score':flow_score(a),'reason':'multi-timeframe rotation setup','trade_setup':setup,'flow_confidence':conf,'relative_strength_to_btc':a.get('relative_strength_to_btc'),'flow_proxy_score':(a.get('multitimeframe') or {}).get('flow_proxy_score'),'flow_notes':a.get('flow_notes') or [],'content_intent':'explain_capital_rotation'})
    # Every materially interesting, evidence-backed research finding becomes an
    # editorial candidate. Later routing, originality, duplicate, Jev and elite
    # gates still decide whether and when it actually publishes.
    for s,r in rmap.items():
        score=research_score(r)
        if score<45:continue
        missing=len(rows(r.get('missing_evidence')))
        discovery_score=clamp(max(score, n(r.get('information_advantage_score'))*.7+n(r.get('undercoverage_score'))*.3))
        base={'type':'research','symbol':s,'score':clamp(score),'research':r,'data_quality':'RESEARCH','reason':'original research finding with evidence and information advantage'}
        stories.append({**base,'category':'research_insight','content_intent':'explain_new_research_finding'})
        if n(r.get('undercoverage_score'))>=65 and n(r.get('information_advantage_score'))>=65:
            stories.append({**base,'category':'data_surprise','score':clamp(score+3),'content_intent':'explain_undercovered_data_signal'})
        if n(r.get('evidence_score'))>=75 and missing==0:
            stories.append({**base,'category':'education','score':clamp(score+2),'content_intent':'teach_a_verified_market_lesson'})
        if r.get('mechanism') or r.get('mechanism_explanation') or r.get('why_now'):
            stories.append({**base,'category':'market_mechanism','score':clamp(score+2),'content_intent':'explain_how_the_market_mechanism_works'})
    for st in stories:
        st['score']=clamp(st['score']+(8 if st.get('type')=='research' else 6 if st.get('type')=='flow' else 4 if st.get('category') in {'next_gainer_candidate','next_loser_candidate','creator_signal_outcome','follow_up','comparison'} else 0))
        if st['symbol']==sym(selected.get('symbol')) and selected.get('category'):st['score']=clamp(st['score']+3);st['authoritative_hint']=True
    prefs=feedback.get('learned_preferences') or {};preferred=str((prefs.get('format') or {}).get('prefer') or '').lower()
    for st in stories:
        if preferred and FORMAT.get(st.get('category',''),'').lower()==preferred:st['score']=clamp(st['score']+3)
    stories.sort(key=lambda x:(x['score'],1 if x.get('type') in {'research','flow'} or x.get('authoritative_ranking') else 0),reverse=True);best=stories[0] if stories else None
    publish=bool(best and best['score']>=72 and best.get('symbol'))
    reason='no_candidates' if not best else ('best_candidate_below_quality_threshold' if not publish else 'high_intent_cross_lane_opportunity')
    out_selected=None
    if publish:
        out_selected={'category':best['category'],'symbol':best['symbol']+'USDT' if best['symbol'] not in {'XAUUSD','XAGUSD'} else best['symbol'],'reason':safe_reason(best),'score':best['score'],'lane':best['type'],'content_intent':best.get('content_intent','')}
        for k in ('title','source','url','published_at','trade_setup','flow_confidence','relative_strength_to_btc','flow_proxy_score','flow_notes','research','early_mover','confirmation_required','ranker_score','authoritative_ranking'):
            if k in best:out_selected[k]=best[k]
    chart=[best['symbol'] for best in [best] if best and valid(best.get('symbol')) and best.get('type') in {'market','flow','research','news'}]
    visual_type='candlestick_chart' if chart else 'none'
    brief={'generated_at':datetime.now(timezone.utc).isoformat(),'director_version':'8.0-discovery-to-publication','run_ai':publish,'reason':reason,'primary_story':{'symbol':out_selected.get('symbol','') if out_selected else '','lane':best.get('category') if best else None,'score':best.get('score') if best else 0,'chart_symbols':chart,'content_intent':best.get('content_intent','') if best else ''} if best else {},'authoritative_selection':out_selected,'ranked_stories':stories[:40],'lane_scores':{'news':max([x['score'] for x in stories if x['type']=='news'],default=0),'flow':max([x['score'] for x in stories if x['type']=='flow'],default=0),'market':max([x['score'] for x in stories if x['type']=='market'],default=0),'research':max([x['score'] for x in stories if x['type']=='research'],default=0)},'recommended_format':FORMAT.get(best.get('category'),'DEEP RESEARCH RADAR') if best else 'DEEP RESEARCH RADAR','narrative_engine':NARRATIVE.get(best.get('category'),'deep_research_radar') if best else 'deep_research_radar','visual_plan':{'provider':'TradingView' if chart else 'none','layout':'single_panel','symbols':chart,'timeframe':'1H','custom_overlays':True,'type':visual_type,'required':bool(out_selected),'reason':'Visual evidence required when technically available.'},'interaction_plan':{'primary_goal':'specific conversation','question_rule':'exactly one story-specific question','avoid':['What do you think?','Thoughts?','Bullish, bearish, or wait?']},'monetization_path':{'cashtag_required':bool(out_selected),'chart_or_widget_preferred':bool(out_selected),'real_trade_widget_if_verified':True,'revenue_must_be_account_verified':True,'no_clickbait':True},'writing_contract':['Choose differentiated high-information discoveries, lessons, mechanisms, research and market opportunities over raw price movement.','Every selected discovery must have a clear claim, evidence, why-it-matters, and a falsifiable or teachable condition; trade levels are only required for trading lanes.','Capital-flow LONG/SHORT content is conditional and requires trigger plus invalidation.','Early-mover candidates are confirmation watches unless a complete setup is independently verified.','Never invent targets, stops, prices, sources, personal trades, revenue or outcomes.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8');pre['content_director_4']=brief;pre['selected_opportunity']=out_selected;PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'7.2-schema-safe-authoritative-ranking','publish':publish,'reason':reason,'selected':out_selected,'lane_scores':brief['lane_scores']},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
