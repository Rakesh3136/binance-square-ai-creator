"""Creator 4.3 executive story director: select the strongest publishable story, not merely the strongest ticker."""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/content_director_brief.json'
LANES={'breaking_news':32,'news_market_impact':28,'technical_breakout':23,'top_mover':18,'volume_anomaly':23,'liquidation':24,'new_listing':27,'macro':27,'creator_signal_outcome':27,'education':12,'comparison':17,'follow_up':23,'watchlist':18}
FORMAT_BY_CATEGORY={'breaking_news':'BREAKING NEWS + MARKET IMPACT','news_and_macro':'NEWS + CHART','top_gainers':'TOP MOVERS','top_losers':'BREAKOUT / FAKEOUT','high_volatility':'LIQUIDATION STORY','volume_leaders':'DATA SURPRISE','new_listings':'NEW LISTING WATCH','technical_setup':'TRADINGVIEW CHART CHALLENGE','comparison':'COIN VS COIN','education':'EDUCATION FROM LIVE CHART','creator_signal_outcome':'CREATOR CALL OUTCOME','follow_up':'FOLLOW-UP / UPDATE','macro':'MACRO + MARKET IMPACT'}

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def num(x):
    try:return float(x)
    except Exception:return 0.0
def text(x):return str(x or '').strip()
def symbol(x):
    s=text(x).upper().replace('$','').replace('BINANCE:',''); return s[:-4] if s.endswith('USDT') else s
def valid(s):return bool(re.fullmatch(r'[A-Z0-9]{1,15}',s))
def news_score(a):
    t=(text(a.get('title'))+' '+text(a.get('summary'))+' '+text(a.get('description'))).lower(); score=0
    for k,w in [('breaking',14),('hack',18),('exploit',18),('etf',14),('sec',11),('fed',11),('rate',9),('inflation',9),('listing',13),('upgrade',9),('partnership',7),('regulation',10),('liquidation',11),('whale',10),('airdrop',8),('unlock',8),('gold',12),('silver',12)]:
        if k in t:score+=w
    return score
def collect_market(m):
    out=[]
    for g in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in m.get(g) or []:
            if isinstance(x,dict) and x.get('symbol'):out.append(x)
    return out
def market_story(x):
    move=abs(num(x.get('price_change_percent'))); vol=num(x.get('quote_volume_usdt') or x.get('quote_volume')); signal=num(x.get('content_signal_score')); rng=num(x.get('intraday_range_percent'))
    lane='top_mover'
    if rng>=20 or move>=25:lane='liquidation'
    elif signal>=70:lane='technical_breakout'
    elif vol>=1e8:lane='volume_anomaly'
    return {'lane':lane,'symbol':symbol(x['symbol']),'score':round(LANES[lane]+min(30,move*.55)+min(18,signal*.18)+min(12,vol/1e8)+min(8,rng*.15),2),'price_change_percent':num(x.get('price_change_percent')),'last_price':num(x.get('last_price')),'quote_volume_usdt':vol,'intraday_range_percent':rng,'content_signal_score':signal,'has_1h_ohlcv':bool(x.get('candles_1h')),'reason':'verified live market move, liquidity or attention signal'}
def main():
    market,news,pre=load(MARKET),load(NEWS),load(PREFLIGHT); selected=pre.get('selected_opportunity') or {}; selected_symbol=symbol(selected.get('symbol') or selected.get('topic')); items=collect_market(market); stories=[market_story(x) for x in items]
    news_stories=[]
    for a in news.get('articles') or []:
        if not isinstance(a,dict):continue
        ns=float(a.get('news_score') or news_score(a)); title=text(a.get('title')); low=(title+' '+text(a.get('summary'))).lower()
        if ns<55 or not title:continue
        syms=[symbol(x) for x in (a.get('symbols') or []) if valid(symbol(x))]
        if not syms:
            if 'gold' in low and 'silver' in low:syms=['XAUUSD','XAGUSD']
            elif 'gold' in low:syms=['XAUUSD']
            elif 'silver' in low:syms=['XAGUSD']
        news_stories.append({'lane':'breaking_news' if ns>=70 else 'news_market_impact','score':round(ns,2),'title':title[:200],'url':text(a.get('url') or a.get('link')),'source':text(a.get('source')),'published_at':text(a.get('published_at')),'symbols':syms,'reason':'fresh source contains a material catalyst'})
    news_stories.sort(key=lambda x:x['score'],reverse=True); stories.extend(news_stories); stories.sort(key=lambda x:x['score'],reverse=True)
    category=text(selected.get('category')).lower(); selected_news=bool(selected.get('news_title')); best_news=news_stories[0] if news_stories else None
    # Executive rule: a material fresh news story beats a generic market mover, unless the selected lane is already a specific follow-up/creator outcome.
    protected=category in {'creator_signal_outcome','follow_up'}
    if best_news and not selected_news and not protected and best_news['score']>=65:
        selected=dict(selected)
        selected.update({'category':'breaking_news' if best_news['score']>=70 else 'news_and_macro','symbol':best_news['symbols'][0] if best_news['symbols'] else selected_symbol,'news_title':best_news['title'],'news_url':best_news['url'],'news_source':best_news['source'],'news_published_at':best_news['published_at'],'news_score':best_news['score'],'reason':'Executive story director promoted the strongest fresh material news opportunity.'})
        category=text(selected.get('category')).lower(); selected_symbol=symbol(selected.get('symbol') or selected.get('topic')); selected_news=True
    recommended=FORMAT_BY_CATEGORY.get(category,'TRADINGVIEW CHART CHALLENGE'); item=next((x for x in items if symbol(x.get('symbol'))==selected_symbol),None)
    primary={'lane':category or 'market_opportunity','symbol':selected_symbol,'score':num(selected.get('adjusted_score') or selected.get('raw_score')),'reason':text(selected.get('reason') or 'verified selected market opportunity'),'source':'content_director_authoritative_selection'}
    if selected.get('news_title'):primary.update({'news_title':text(selected.get('news_title'))[:240],'news_url':text(selected.get('news_url')),'news_source':text(selected.get('news_source')),'news_published_at':text(selected.get('news_published_at')),'news_score':num(selected.get('news_score'))})
    if item:primary.update({'price_change_percent':num(item.get('price_change_percent')),'last_price':num(item.get('last_price')),'quote_volume_usdt':num(item.get('quote_volume_usdt') or item.get('quote_volume')),'intraday_range_percent':num(item.get('intraday_range_percent')),'content_signal_score':num(item.get('content_signal_score')),'has_1h_ohlcv':bool(item.get('candles_1h'))})
    related=[]
    if selected.get('news_title'):
        for a in news_stories:
            if a.get('title')==selected.get('news_title'):related=[symbol(x) for x in a.get('symbols') if valid(symbol(x))];break
    if category=='comparison':related=[symbol(x.get('symbol')) for x in sorted(items,key=lambda x:num(x.get('content_signal_score')),reverse=True) if symbol(x.get('symbol'))!=selected_symbol][:1]
    low=(text(selected.get('news_title'))+' '+text(selected.get('reason'))).lower()
    if 'gold' in low and 'silver' in low:related=['XAUUSD','XAGUSD']
    elif 'gold' in low and not related:related=['XAUUSD']
    elif 'silver' in low and not related:related=['XAGUSD']
    chart_symbols=[]
    for s in [selected_symbol,*related]:
        if valid(s) and s not in chart_symbols:chart_symbols.append(s)
    if selected.get('news_title') and len(chart_symbols)<2:chart_symbols.append('BTC')
    chart_symbols=chart_symbols[:2]
    brief={'generated_at':datetime.now(timezone.utc).isoformat(),'director_version':'4.3','algorithm_policy':'Infer only from observable performance. Never claim knowledge of a private ranking algorithm.','primary_story':{**primary,'chart_symbols':chart_symbols},'recommended_format':recommended,'authoritative_selection':selected,'news_context':news_stories[:10],'ranked_stories':stories[:40],'coverage_mix':['breaking_news','news_market_impact','macro','technical_breakout','top_mover','volume_anomaly','liquidation','new_listing','creator_signal_outcome','education','comparison','follow_up','watchlist'],'visual_plan':{'provider':'TradingView','layout':'two_panel' if len(chart_symbols)>1 else 'single_panel','symbols':chart_symbols,'timeframe':'1H','custom_overlays':False},'story_rules':['Fresh material news outranks a generic mover.','A specific creator-call outcome/follow-up can outrank generic news when it has verified evidence.','News posts lead with the actual verified event and source.','Every story must answer why-now and what-to-watch, not just repeat price data.','Use two clean TradingView charts only when the second asset adds context.','Macro gold/silver stories may use OANDA TradingView symbols; crypto stories use Binance TradingView symbols.','No custom panel may cover candles or price data.','Targets/SL/10x/20x are conditional scenarios only.','Never invent facts, sources, calls, prices, targets or outcomes.','Prefer a distinctive angle over a generic recap.','Rotate hooks, formats, narrative structures and CTA questions.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8');pre['content_director_4']=brief;pre['selected_opportunity']=selected;pre['content_director_instruction']=f'Use authoritative asset ${selected_symbol}, format {recommended}, and TradingView visual symbols {chart_symbols}.';PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'4.3','symbol':selected_symbol,'format':recommended,'chart_symbols':chart_symbols,'news_candidates':len(news_stories),'executive_promotion':bool(best_news and selected_news and not category in {"creator_signal_outcome","follow_up"})},indent=2))
if __name__=='__main__':main()
