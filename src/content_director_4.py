"""Creator 4.0 content director.

The preflight selector is authoritative. This stage enriches that selection with
ranked market/news opportunities instead of silently choosing a different asset.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'
NEWS=ROOT/'data/live/news_snapshot.json'
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
OUT=ROOT/'data/live/content_director_brief.json'

LANES={
 'breaking_news':24,'news_market_impact':22,'technical_breakout':20,'top_mover':15,
 'volume_anomaly':18,'liquidation':18,'new_listing':21,'macro':22,
 'creator_signal_outcome':20,'education':10,'comparison':13,'follow_up':17
}

FORMAT_BY_CATEGORY={
 'top_gainers':'TOP MOVERS', 'top_losers':'BREAKOUT / FAKEOUT',
 'high_volatility':'LIQUIDATION STORY', 'volume_leaders':'DATA SURPRISE',
 'new_listings':'NEW LISTING WATCH', 'technical_setup':'TRADINGVIEW CHART CHALLENGE',
 'comparison':'COIN VS COIN', 'education':'EDUCATION FROM LIVE CHART'
}

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def num(x):
    try:return float(x)
    except Exception:return 0.0

def text(x):return str(x or '').strip()

def symbol(x):
    s=text(x).upper().replace('$','')
    return s[:-4] if s.endswith('USDT') else s

def news_score(a):
    t=(text(a.get('title'))+' '+text(a.get('summary'))+' '+text(a.get('description'))).lower()
    score=0
    for k,w in [('breaking',12),('hack',16),('exploit',16),('etf',13),('sec',10),('fed',10),('rate',8),('inflation',8),('listing',12),('upgrade',8),('partnership',6),('regulation',9),('liquidation',10),('whale',9)]:
        if k in t:score+=w
    return score

def market_item(market, wanted):
    target=symbol(wanted)
    groups=('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market')
    items=[]
    for g in groups:
        for x in market.get(g) or []:
            if isinstance(x,dict) and x.get('symbol'):
                items.append(x)
    for x in items:
        if symbol(x.get('symbol'))==target:return x
    return next((x for x in items if x.get('candles_1h')), None)

def main():
    market=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT)
    selected=pre.get('selected_opportunity') or {}
    if not isinstance(selected,dict):selected={}
    selected_symbol=symbol(selected.get('symbol') or selected.get('topic'))
    item=market_item(market,selected_symbol) if selected_symbol else None

    stories=[]
    for lane,groups in [('top_mover',['top_gainers','top_losers']),('volume_anomaly',['highest_volume']),('technical_breakout',['top_content_signals']),('new_listing',['new_listing_market'])]:
        for g in groups:
            for x in market.get(g) or []:
                if not isinstance(x,dict) or not x.get('symbol'):continue
                move=abs(num(x.get('price_change_percent'))); vol=num(x.get('quote_volume_usdt') or x.get('quote_volume')); signal=num(x.get('content_signal_score'))
                score=LANES[lane]+min(28,move*0.45)+min(16,signal*0.16)+min(10,vol/1e8)
                stories.append({'lane':lane,'symbol':symbol(x['symbol']),'score':round(score,2),'price_change_percent':num(x.get('price_change_percent')),'quote_volume_usdt':vol,'content_signal_score':signal,'reason':'verified market move/attention signal'})

    news_stories=[]
    for a in (news.get('articles') or news.get('items') or []):
        if not isinstance(a,dict):continue
        ns=news_score(a)
        if ns<=0:continue
        news_stories.append({'lane':'breaking_news' if ns>=16 else 'news_market_impact','score':round(LANES['breaking_news']+ns,2),'title':text(a.get('title'))[:180],'url':text(a.get('url') or a.get('link')),'reason':'fresh news contains a material crypto catalyst'})
    stories.extend(news_stories)
    stories.sort(key=lambda x:x['score'],reverse=True)

    category=text(selected.get('category') or selected.get('reason') or '').lower()
    experiment=((pre.get('engagement_strategy') or {}).get('experiment') or {})
    experiment_format=text(experiment.get('format')).upper()
    if selected_symbol:
        primary={
            'lane':category or 'market_opportunity',
            'symbol':selected_symbol,
            'score':num(selected.get('adjusted_score') or selected.get('raw_score') or 0),
            'reason':text(selected.get('reason') or 'verified selected market opportunity'),
            'source':'editorial_preflight_authoritative_selection'
        }
        if item:
            primary.update({
                'price_change_percent':num(item.get('price_change_percent')),
                'last_price':num(item.get('last_price')),
                'quote_volume_usdt':num(item.get('quote_volume_usdt') or item.get('quote_volume')),
                'intraday_range_percent':num(item.get('intraday_range_percent')),
                'content_signal_score':num(item.get('content_signal_score')),
                'has_1h_ohlcv':bool(item.get('candles_1h'))
            })
        # Prefer the experiment only when it is compatible with the selected asset.
        recommended=experiment_format or FORMAT_BY_CATEGORY.get(category,'TRADINGVIEW CHART CHALLENGE')
        if recommended in {'BREAKING NEWS + MARKET IMPACT','NEWS REACTION'} and not news_stories:
            recommended=FORMAT_BY_CATEGORY.get(category,'TRADINGVIEW CHART CHALLENGE')
    else:
        # News without an identifiable tradeable symbol is useful as research,
        # but cannot become the authoritative chart asset.
        market_candidates=[x for x in stories if x.get('symbol')]
        primary=market_candidates[0] if market_candidates else {'lane':'education','score':10,'reason':'no symbol-bearing opportunity passed the evidence threshold'}
        recommended=FORMAT_BY_CATEGORY.get(primary.get('lane'),'TRADINGVIEW CHART CHALLENGE')

    brief={
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'director_version':'4.1',
      'algorithm_policy':'Observed engagement patterns are experiments, never knowledge of a hidden platform algorithm.',
      'primary_story':primary,
      'recommended_format':recommended,
      'authoritative_selection':selected,
      'news_context':news_stories[:8],
      'ranked_stories':stories[:30],
      'coverage_mix':['breaking_news','macro','technical_breakout','top_mover','volume_anomaly','new_listing','liquidation','creator_signal_outcome','education','comparison','follow_up'],
      'story_rules':[
        'The preflight selected symbol is authoritative and must remain synchronized through writing and rendering.',
        'Prefer a concrete catalyst, number, level or surprising observation over generic price recaps.',
        'Use TradingView for every single-asset market post; chart-only means no custom overlays covering candles.',
        'Use news as context only when it is fresh and relevant; never invent a relationship between an article and a coin.',
        'Use creator-call outcomes only after fresh market data verifies the original public call.',
        'Frame 10x/20x ideas as conditional scenarios with market-cap math, never as promises.',
        'End with one easy, real interaction question.'
      ]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    pre['content_director_4']=brief
    pre['content_director_instruction']=f"Use authoritative asset ${selected_symbol} and format {recommended}. Never replace the selected asset downstream."
    PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','director':'4.1','symbol':selected_symbol,'format':recommended,'ranked':len(stories)},indent=2))

if __name__=='__main__':main()
