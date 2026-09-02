"""Creator 4.2 content intelligence director.

Chooses the strongest *story*, not merely the strongest mover. The selected
asset remains authoritative all the way through writing and chart rendering.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/content_director_brief.json'

LANES={'breaking_news':28,'news_market_impact':24,'technical_breakout':23,'top_mover':17,'volume_anomaly':21,'liquidation':22,'new_listing':24,'macro':24,'creator_signal_outcome':23,'education':12,'comparison':16,'follow_up':21,'watchlist':18}
FORMAT_BY_CATEGORY={'breaking_news':'BREAKING NEWS + MARKET IMPACT','news_and_macro':'NEWS + CHART','top_gainers':'TOP MOVERS','top_losers':'BREAKOUT / FAKEOUT','high_volatility':'LIQUIDATION STORY','volume_leaders':'DATA SURPRISE','new_listings':'NEW LISTING WATCH','technical_setup':'TRADINGVIEW CHART CHALLENGE','comparison':'COIN VS COIN','education':'EDUCATION FROM LIVE CHART','creator_signal_outcome':'CREATOR CALL OUTCOME','follow_up':'FOLLOW-UP / UPDATE'}
ROTATION=['BREAKING NEWS + MARKET IMPACT','NEWS + CHART','TRADINGVIEW CHART CHALLENGE','TOP MOVERS','DATA SURPRISE','LIQUIDATION STORY','NEW LISTING WATCH','MACRO + MARKET IMPACT','CREATOR CALL OUTCOME','EDUCATION FROM LIVE CHART','COIN VS COIN','FOLLOW-UP / UPDATE']

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def num(x):
    try:return float(x)
    except Exception:return 0.0

def text(x):return str(x or '').strip()

def symbol(x):
    s=text(x).upper().replace('$','').replace('BINANCE:','')
    return s[:-4] if s.endswith('USDT') else s

def news_score(a):
    t=(text(a.get('title'))+' '+text(a.get('summary'))+' '+text(a.get('description'))).lower(); score=0
    for k,w in [('breaking',14),('hack',18),('exploit',18),('etf',14),('sec',11),('fed',11),('rate',9),('inflation',9),('listing',13),('upgrade',9),('partnership',7),('regulation',10),('liquidation',11),('whale',10),('airdrop',8),('unlock',8)]:
        if k in t: score+=w
    return score

def collect_market(market):
    groups=('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market')
    out=[]
    for g in groups:
        for x in market.get(g) or []:
            if isinstance(x,dict) and x.get('symbol'):out.append(x)
    return out

def main():
    market=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT); selected=pre.get('selected_opportunity') or {}
    if not isinstance(selected,dict):selected={}
    selected_symbol=symbol(selected.get('symbol') or selected.get('topic'))
    market_items=collect_market(market)
    stories=[]
    for x in market_items:
        move=abs(num(x.get('price_change_percent'))); vol=num(x.get('quote_volume_usdt') or x.get('quote_volume')); signal=num(x.get('content_signal_score')); rng=num(x.get('intraday_range_percent'))
        lane='top_mover'
        if rng>=20 or move>=25: lane='liquidation'
        elif signal>=70: lane='technical_breakout'
        elif vol>=1e8: lane='volume_anomaly'
        score=LANES[lane]+min(30,move*.55)+min(18,signal*.18)+min(12,vol/1e8)+min(8,rng*.15)
        stories.append({'lane':lane,'symbol':symbol(x['symbol']),'score':round(score,2),'price_change_percent':num(x.get('price_change_percent')),'last_price':num(x.get('last_price')),'quote_volume_usdt':vol,'intraday_range_percent':rng,'content_signal_score':signal,'has_1h_ohlcv':bool(x.get('candles_1h')),'reason':'verified live market move, liquidity or attention signal'})
    news_stories=[]
    for a in (news.get('articles') or news.get('items') or []):
        if not isinstance(a,dict):continue
        ns=float(a.get('news_score') or news_score(a)); title=text(a.get('title'))
        if ns<55:continue
        news_stories.append({'lane':'breaking_news' if ns>=70 else 'news_market_impact','score':round(ns,2),'title':title[:200],'url':text(a.get('url') or a.get('link')),'source':text(a.get('source')),'published_at':text(a.get('published_at')),'symbols':a.get('symbols') or [],'reason':'fresh source contains a material catalyst'})
    news_stories.sort(key=lambda x:x['score'],reverse=True)
    stories.extend(news_stories); stories.sort(key=lambda x:x['score'],reverse=True)

    experiment=((pre.get('engagement_strategy') or {}).get('experiment') or {}); expfmt=text(experiment.get('format')).upper()
    category=text(selected.get('category') or '').lower()
    recommended=FORMAT_BY_CATEGORY.get(category,'TRADINGVIEW CHART CHALLENGE')
    if selected_symbol:
        item=next((x for x in market_items if symbol(x.get('symbol'))==selected_symbol),None)
        primary={'lane':category or 'market_opportunity','symbol':selected_symbol,'score':num(selected.get('adjusted_score') or selected.get('raw_score') or 0),'reason':text(selected.get('reason') or 'verified selected market opportunity'),'source':'editorial_preflight_authoritative_selection'}
        if selected.get('news_title'):
            primary.update({'news_title':text(selected.get('news_title'))[:240],'news_url':text(selected.get('news_url')),'news_source':text(selected.get('news_source')),'news_published_at':text(selected.get('news_published_at')),'news_score':num(selected.get('news_score'))})
        if item: primary.update({'price_change_percent':num(item.get('price_change_percent')),'last_price':num(item.get('last_price')),'quote_volume_usdt':num(item.get('quote_volume_usdt') or item.get('quote_volume')),'intraday_range_percent':num(item.get('intraday_range_percent')),'content_signal_score':num(item.get('content_signal_score')),'has_1h_ohlcv':bool(item.get('candles_1h'))})
        # News is authoritative: do not let an engagement experiment turn a breaking story back into a generic mover post.
        if category not in {'breaking_news','news_and_macro'} and expfmt in ROTATION and (not news_stories or expfmt not in {'BREAKING NEWS + MARKET IMPACT','NEWS + CHART','MACRO + MARKET IMPACT'}): recommended=expfmt
        if category in {'breaking_news','news_and_macro'}: recommended=FORMAT_BY_CATEGORY[category]
        if category in {'creator_signal_outcome','follow_up'}: recommended=FORMAT_BY_CATEGORY[category]
    else:
        primary=next((x for x in stories if x.get('symbol')),{'lane':'education','score':12,'reason':'no symbol-bearing opportunity passed the evidence threshold'})
        recommended=FORMAT_BY_CATEGORY.get(primary.get('lane'),'TRADINGVIEW CHART CHALLENGE')

    recent=pre.get('recent_performance_context') or {}; recent_formats=recent.get('recent_formats') or []
    coverage=['breaking_news','news_market_impact','macro','technical_breakout','top_mover','volume_anomaly','liquidation','new_listing','creator_signal_outcome','education','comparison','follow_up','watchlist']
    brief={'generated_at':datetime.now(timezone.utc).isoformat(),'director_version':'4.2','algorithm_policy':'Use observed performance only as an experiment. Never claim knowledge of a private ranking algorithm.','primary_story':primary,'recommended_format':recommended,'authoritative_selection':selected,'news_context':news_stories[:10],'ranked_stories':stories[:40],'coverage_mix':coverage,'recent_format_context':recent_formats,'story_rules':['Fresh material news is a first-class opportunity and outranks a generic mover.','The preflight selected symbol is authoritative downstream.','Prefer a specific catalyst, surprise, level or measurable change over generic recaps.','Single-asset market posts require a TradingView chart; no custom panel may cover candles or the price area.','Creator calls become follow-ups only after fresh market data verifies the move; attribute the original source and never claim we predicted it.','Targets, stop/invalidation and 10x/20x scenarios must be conditional and evidence-based.','Never invent news, sources, creator calls, prices, targets, volume or engagement.','One real question per post; no begging for likes/follows.','Rotate formats and narrative structures so consecutive posts do not feel templated.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    pre['content_director_4']=brief; pre['content_director_instruction']=f'Use authoritative asset ${selected_symbol} and format {recommended}; if news is selected, lead with the verified headline and source before discussing price.'
    PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','director':'4.2','symbol':selected_symbol,'format':recommended,'news_candidates':len(news_stories),'ranked':len(stories)},indent=2))

if __name__=='__main__':main()
