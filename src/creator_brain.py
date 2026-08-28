from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
PATHS={
    'market':'data/live/market_snapshot.json','news':'data/live/news_snapshot.json',
    'preflight':'data/live/editorial_preflight.json','authoritative':'data/live/authoritative_opportunity.json',
    'strategy':'analytics/strategy_memory.json','patterns':'data/intelligence/creator_patterns.json',
    'stories':'data/intelligence/story_memory.json','audience':'data/intelligence/audience_profile.json',
    'experiments':'data/intelligence/experiment_queue.json','timing':'data/intelligence/market_timing.json',
    'visual':'data/intelligence/visual_decision.json','thesis':'data/intelligence/thesis_ledger.json',
    'evolution':'data/live/creator_evolution_state.json','performance':'data/intelligence/performance_feedback.json'
}
OUT=ROOT/'data/live/creator_brain_decision.json'

def read(rel):
    try:
        x=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def recent_news(news):
    items=[x for x in (news.get('articles') or []) if isinstance(x,dict) and x.get('title')]
    return items[:30]

def news_priority(news):
    items=recent_news(news)
    if not items:return 0
    score=0
    for x in items[:12]:
        cat=str(x.get('category','')).lower()
        title=str(x.get('title','')).lower()
        if cat in {'macro_official','regulation_official'}: score+=5
        elif cat=='crypto_news': score+=2
        if any(k in title for k in ('breaking','etf','fed','sec','regulation','hack','exploit','listing','approval','launch','upgrade')): score+=3
    return score

def main():
    d={k:read(v) for k,v in PATHS.items()}
    market,news,preflight,authoritative=d['market'],d['news'],d['preflight'],d['authoritative']
    strategy,patterns,stories,audience,experiments,timing,visual,thesis,evolution,performance=(d[k] for k in ('strategy','patterns','stories','audience','experiments','timing','visual','thesis','evolution','performance'))
    engagement=preflight.get('engagement_strategy') or {}
    experiment=engagement.get('experiment') or {}
    selected_pf=authoritative or preflight.get('selected_opportunity') or {}
    recent=(strategy.get('recent_observations') or strategy.get('recent_performance_observations') or [])[-20:]
    passive=[x for x in recent if float(x.get('views',x.get('viewCount',0)) or 0)>0 and float(x.get('replies',x.get('replyCount',0)) or 0)==0 and float(x.get('followers_gained',0) or 0)==0]
    active=stories.get('active_stories') or []
    used=[str(x.get('symbol','')).upper().replace('USDT','') for x in recent if x.get('symbol')]
    candidates=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and x.get('symbol'): candidates.append(x)
    candidates=sorted(candidates,key=lambda x:float(x.get('content_signal_score',0) or 0)+abs(float(x.get('price_change_percent',0) or 0)),reverse=True)
    requested_symbol=str(selected_pf.get('symbol') or '').upper().replace('USDT','')
    chosen=next((x for x in candidates if str(x.get('symbol','')).upper().replace('USDT','')==requested_symbol),None)
    if chosen is None: chosen={'symbol':requested_symbol} if requested_symbol else (candidates[0] if candidates else {})
    symbol=requested_symbol or str(chosen.get('symbol','')).upper().replace('USDT','')

    formats=['CHOICE','CHART BREAKDOWN','TOP GAINER/LOSER','VOLUME SURGE','BREAKOUT/FAKEOUT','TARGET MAP','NEWS REACTION','NEWS + CHART','LIQUIDATION STORY','NEW LISTING WATCH','COIN VS COIN','DATA SURPRISE','CREATOR CALL OUTCOME','FOLLOW-UP/UPDATE','EDUCATION']
    current=str(experiment.get('format') or 'CHOICE').upper()
    queue=[x.get('format') for x in experiments.get('queue',[]) if isinstance(x,dict) and x.get('status')=='READY']
    pool=[f for f in queue+formats if f]
    winner_formats=performance.get('winner_formats') or {}
    winner_allowed=bool(performance.get('winner_promotion_allowed',False))
    best_learned=next((fmt for fmt,_ in sorted(winner_formats.items(),key=lambda kv:kv[1],reverse=True) if fmt),None)
    np=news_priority(news)
    # News is now a first-class lane. A strong recent official/crypto headline can
    # override the ordinary experiment rotation; otherwise NEWS + CHART is used
    # periodically so the account does not become technical-only.
    if np>=8 and recent_news(news):
        next_format='NEWS + CHART' if symbol else 'NEWS REACTION'
    elif np>=4 and recent_news(news) and current not in {'NEWS REACTION','NEWS + CHART'} and len(recent)%4==0:
        next_format='NEWS REACTION'
    elif winner_allowed and best_learned and best_learned in pool:
        next_format=best_learned
    else:
        next_format=next((f for f in pool if f!=current),current) if passive else (current if current in pool else formats[0])

    audience_signals=audience.get('signals') or {}
    reply_rate=float(audience_signals.get('replies_per_view',0) or 0)
    category=str(selected_pf.get('category','')).lower()
    chart_first=category in {'top_gainers','top_losers','high_volatility','technical_setup','creator_signal_outcome'} or next_format in {'CHART BREAKDOWN','BREAKOUT/FAKEOUT','TARGET MAP','NEWS + CHART'}
    visual_decision=dict(visual or {})
    if chart_first:
        visual_decision.update({'type':'candlestick_chart','required':True,'reason':'TradingView chart-first editorial lane','provider':'TradingView'})
    news_items=recent_news(news)
    news_context=[{'source':x.get('source'),'category':x.get('category'),'title':x.get('title'),'summary':x.get('summary'),'published_at':x.get('published_at'),'url':x.get('url')} for x in news_items[:12]]
    decision={
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'decision':'CREATE_ORIGINAL_EXPERIMENT','phase':evolution.get('phase','mature_creator'),
        'symbol':symbol,'editorial_format':next_format,
        'conversation_goal':'reply' if passive or reply_rate<0.005 else 'meaningful_engagement',
        'story_continuity':bool(active),'avoid_recent_symbols':used[:5],
        'market_phase':(next((x for x in timing.get('items',[]) if str(x.get('symbol','')).upper().replace('USDT','')==symbol),{}) or {}).get('phase','UNKNOWN'),
        'visual_decision':visual_decision,'audience_signals':audience_signals,
        'experiment_queue':experiments.get('queue',[])[:12],'thesis_context':thesis.get('theses',[])[-10:],
        'reason':'Balance live market opportunities, verified news, technical evidence and learned audience signals.',
        'research_inputs':{'market_candidates':len(candidates),'fresh_news':len(news_items),'news_priority':np,'active_stories':len(active)},
        'news_context':news_context,'optimization_policy':evolution.get('learning_policy',{}),
        'benchmark_patterns':patterns,'story_context':stories,
        'learning_context':{'recent_observations':recent,'passive_recent_count':len(passive),'performance_feedback':performance},
        'preflight_opportunity':selected_pf,
        'technical_requirements':{'for_chart_posts':['current price','support','resistance','TP1/target when supported','SL/invalidation when supported'],'source':'fresh 1H OHLCV','visual_provider':'TradingView'},
        'editorial_requirements':{'news_is_first_class_lane':True,'compare_news_and_market':True,'use_news_plus_chart_when_material':True,'never_invent_news':True},
        'guardrails':['Never invent facts.','Never copy another creator.','Never fabricate performance or revenue.','Use real market data only.','Promote winners only after verified samples.','Retire repeated failures only after enough observations.','Optimize for genuine engagement and eligible attribution, never artificial activity.','Use chart-derived targets/invalidation only when live OHLCV supports them.','Never present a speculative 10x scenario as a certainty.','Never change the frozen primary asset.','Do not state a target or stop as guaranteed.']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'OK','symbol':symbol,'editorial_format':next_format,'chart_required':chart_first,'fresh_news':len(news_items),'news_priority':np,'passive_recent_count':len(passive)}))

if __name__=='__main__':main()
