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
        x=json.loads((ROOT/rel).read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}

def recent_news(news):
    return [x for x in (news.get('articles') or []) if isinstance(x,dict) and x.get('title')][:30]

def news_priority(news):
    score=0
    for x in recent_news(news)[:15]:
        cat=str(x.get('category','')).lower(); title=str(x.get('title','')).lower()
        if cat in {'macro_official','regulation_official'}: score+=6
        elif cat in {'crypto_news','exchange_news','listing_news'}: score+=3
        if any(k in title for k in ('breaking','etf','fed','sec','regulation','hack','exploit','listing','approval','launch','upgrade','lawsuit','tariff')): score+=3
    return score

def norm(v):
    return str(v or '').upper().replace('USDT','').replace('$','').strip()

def main():
    d={k:read(v) for k,v in PATHS.items()}
    market,news,preflight,authoritative=d['market'],d['news'],d['preflight'],d['authoritative']
    strategy,patterns,stories,audience,experiments,timing,visual,thesis,evolution,performance=(d[k] for k in ('strategy','patterns','stories','audience','experiments','timing','visual','thesis','evolution','performance'))
    selected=authoritative or preflight.get('selected_opportunity') or {}
    engagement=preflight.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}
    symbol=norm(selected.get('symbol'))
    if not symbol: raise SystemExit('Creator Brain: no frozen/selected symbol')

    recent=(strategy.get('recent_observations') or strategy.get('recent_performance_observations') or [])[-30:]
    passive=[x for x in recent if float(x.get('views',x.get('viewCount',0)) or 0)>0 and float(x.get('replies',x.get('replyCount',0)) or 0)==0 and float(x.get('followers_gained',0) or 0)==0]
    active=stories.get('active_stories') or []
    used=[norm(x.get('symbol')) for x in recent if x.get('symbol')]
    news_items=recent_news(news);np=news_priority(news)
    category=str(selected.get('category') or '').lower()

    lane_map={
        'capital_flow_long':'CAPITAL_FLOW_LONG','capital_flow_short':'CAPITAL_FLOW_SHORT',
        'watchlist':'RESEARCH_RADAR','technical_setup':'TECHNICAL_SETUP',
        'high_volatility':'TECHNICAL_SETUP','top_gainers':'MOMENTUM_DISCOVERY','top_losers':'MOMENTUM_DISCOVERY',
        'volume_leaders':'DATA_SURPRISE','new_listings':'NEW_LISTING','creator_signal_outcome':'CREATOR_CALL_ACCOUNTABILITY',
        'follow_up':'FOLLOW_UP','comparison':'COMPARISON','education':'EDUCATION','breaking_news':'NEWSROOM','news_and_macro':'NEWSROOM',
        'crypto_meme':'CRYPTO_MEME',
    }
    selected_lane=str(selected.get('lane') or '').lower()
    if selected_lane in {'flow','capital_flow'} and category in {'capital_flow_long','capital_flow_short'}: engine=lane_map.get(category)
    else: engine=lane_map.get(category)
    if not engine:
        engine='NEWSROOM' if category in {'news','newsroom'} or selected.get('news_title') else 'COMMUNITY_DEBATE'

    engine_formats={
        'NEWSROOM':['NEWS REACTION','NEWS + CHART','MAJOR NEWS ARTICLE'],
        'TECHNICAL_SETUP':['CHART BREAKDOWN','BREAKOUT/FAKEOUT','TARGET MAP'],
        'MOMENTUM_DISCOVERY':['MOMENTUM + FOLLOW-THROUGH','TOP GAINER/LOSER','CHOICE'],
        'DATA_SURPRISE':['DATA SURPRISE','VOLUME SURGE','COIN VS COIN'],
        'MACRO_NARRATIVE':['NEWS REACTION','NEWS + CHART','COIN VS COIN'],
        'LIQUIDATION_EVENT':['LIQUIDATION STORY','CHART BREAKDOWN','CHOICE'],
        'NEW_LISTING':['NEW LISTING WATCH','CHOICE','CHART BREAKDOWN'],
        'CREATOR_CALL_ACCOUNTABILITY':['CREATOR CALL OUTCOME','FOLLOW-UP/UPDATE','CHART BREAKDOWN'],
        'FOLLOW_UP':['FOLLOW-UP/UPDATE','CREATOR CALL OUTCOME','CHOICE'],
        'COMPARISON':['COIN VS COIN','DATA SURPRISE','CHOICE'],
        'EDUCATION':['EDUCATION','CHART BREAKDOWN','CHOICE'],
        'COMMUNITY_DEBATE':['CHOICE','COIN VS COIN','DATA SURPRISE'],
        'CAPITAL_FLOW_LONG':['CAPITAL FLOW TRADE SETUP','CHART BREAKDOWN','CHOICE'],
        'CAPITAL_FLOW_SHORT':['CAPITAL FLOW TRADE SETUP','CHART BREAKDOWN','CHOICE'],
        'RESEARCH_RADAR':['MARKET RADAR','COIN VS COIN','DATA SURPRISE'],
        'CRYPTO_MEME':['CRYPTO MEME','MARKET MEME','TRADER HUMOR'],
    }
    current=str(experiment.get('format') or '').upper();ready=[str(x.get('format')).upper() for x in experiments.get('queue',[]) if isinstance(x,dict) and x.get('status')=='READY' and x.get('format')]
    options=engine_formats.get(engine,['CHOICE']);winner_formats=performance.get('winner_formats') or {};winner_allowed=bool(performance.get('winner_promotion_allowed',False))
    best_learned=next((str(fmt).upper() for fmt,_ in sorted(winner_formats.items(),key=lambda kv:kv[1],reverse=True) if str(fmt).upper() in options),None)
    if best_learned and winner_allowed:next_format=best_learned
    elif current in options and passive:next_format=next((x for x in options if x!=current),options[0])
    elif ready:next_format=next((x for x in ready if x in options),options[0])
    else:next_format=options[0]

    audience_signals=audience.get('signals') or {};reply_rate=float(audience_signals.get('replies_per_view',0) or 0)
    conversation_goal='meaningful_engagement' if reply_rate>=0.005 else 'specific_reply'
    if engine=='COMMUNITY_DEBATE':conversation_goal='low_friction_choice'
    if engine=='CREATOR_CALL_ACCOUNTABILITY':conversation_goal='credibility_discussion'
    if engine in {'CAPITAL_FLOW_LONG','CAPITAL_FLOW_SHORT'}:conversation_goal='setup_confirmation_discussion'
    if engine=='CRYPTO_MEME':conversation_goal='shareable_reaction'

    visual_decision=dict(visual or {})
    chart_first=next_format in {'CHART BREAKDOWN','BREAKOUT/FAKEOUT','TARGET MAP','NEWS + CHART','CREATOR CALL OUTCOME','MOMENTUM + FOLLOW-THROUGH','CAPITAL FLOW TRADE SETUP'} or engine in {'TECHNICAL_SETUP','CREATOR_CALL_ACCOUNTABILITY','CAPITAL_FLOW_LONG','CAPITAL_FLOW_SHORT'}
    if engine=='CRYPTO_MEME': chart_first=False
    if chart_first:visual_decision.update({'type':'candlestick_chart','required':True,'reason':'Selected story engine requires technical visual evidence','provider':'TradingView'})
    else:visual_decision.update({'required':False if engine=='CRYPTO_MEME' else True,'provider':'TradingView','type':'candlestick_chart' if engine!='CRYPTO_MEME' else 'none','reason':'Use a real market chart when it adds evidence; memes do not require a chart'})

    news_context=[{'source':x.get('source'),'category':x.get('category'),'title':x.get('title'),'summary':x.get('summary'),'published_at':x.get('published_at'),'url':x.get('url')} for x in news_items[:12]]
    decision={'generated_at':datetime.now(timezone.utc).isoformat(),'version':'5.2','decision':'CREATE_STORY_FIRST','phase':evolution.get('phase','mature_creator'),'symbol':symbol,'story_engine':engine,'editorial_format':next_format,'conversation_goal':conversation_goal,'story_continuity':bool(active),'avoid_recent_symbols':used[:8],'market_phase':(next((x for x in timing.get('items',[]) if norm(x.get('symbol'))==symbol),{}) or {}).get('phase','UNKNOWN'),'visual_decision':visual_decision,'audience_signals':audience_signals,'experiment_queue':experiments.get('queue',[])[:12],'thesis_context':thesis.get('theses',[])[-10:],'reason':f'Honor cross-lane selected opportunity {category or "unclassified"} for ${symbol}; build story from its evidence rather than allowing unrelated news to override it.','research_inputs':{'fresh_news':len(news_items),'news_priority':np,'active_stories':len(active),'recent_observations':len(recent)},'news_context':news_context,'optimization_policy':evolution.get('learning_policy',{}),'benchmark_patterns':patterns,'story_context':stories,'learning_context':{'recent_observations':recent,'passive_recent_count':len(passive),'performance_feedback':performance},'preflight_opportunity':selected,'editorial_requirements':{'story_first':True,'selected_opportunity_is_authoritative':True,'news_is_first_class_lane':True,'news_cannot_override_other_selected_lane':True,'use_real_event_before_price_recap':True,'vary_hook_and_rhythm':True,'avoid_generic_price_alerts':True,'build_return_reason':True,'one_clear_conversation_mechanism':True,'use_real_tradingview_when_technical':True,'news_plus_chart_when_material':True,'capital_flow_requires_conditional_setup':True,'meme_is_a_reach_lane_not_a_trade_call':True,'meme_must_be_crypto_relevant_and_original':True,'never_invent_news':True},'creator_identity':{'positioning':'sharp, evidence-aware crypto market observer','recurring_series':['Market Radar','Breakout or Fakeout','Capital Flow Watch','Call Check','One Chart One Lesson','What Everyone Is Missing','Crypto Market Meme'],'goal':'Make each post useful alone while creating a reason to follow the next update.'},'guardrails':['Never invent facts, sources, prices, volume, targets, stops, creator calls or outcomes.','Never copy or imitate another creator.','Never fabricate performance, revenue or follower growth.','Use real market data only.','Promote winning formats only after verified samples.','Do not turn every post into a percentage-move recap.','Do not repeat the same hook, CTA or paragraph rhythm in consecutive cycles.','Optimize for genuine replies, follows and eligible attribution, never artificial activity.','Use chart-derived targets/invalidation only when fresh OHLCV supports them.','Speculative 10x/20x scenarios must be conditional, never guaranteed.','Never change the frozen primary asset.','Meme posts must not masquerade as investment recommendations.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False));print(json.dumps({'status':'OK','version':'5.2','symbol':symbol,'story_engine':engine,'editorial_format':next_format,'chart_required':chart_first,'fresh_news':len(news_items),'news_priority':np}))
if __name__=='__main__':main()
