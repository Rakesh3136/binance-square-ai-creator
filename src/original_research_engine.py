"""Original Research Engine 1.0.
Builds a compact, evidence-first research artifact from authoritative pipeline data.
It does not invent facts and never changes market data.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUB=ROOT/'analytics/publication_log.jsonl'
OUT=ROOT/'data/live/original_research.json'; REPORT=ROOT/'data/intelligence/original_research_report.json'
def load(p,default=None):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {} if default is None else default
def sym(v):return re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())
def main():
    market=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT); selected=pre.get('selected_opportunity') or {}
    symbol=sym(selected.get('symbol') or market.get('top_signal',{}).get('symbol') or pre.get('symbol'))
    item=None
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and sym(x.get('symbol'))==symbol:item=x;break
        if item:break
    articles=[]
    for a in news.get('articles') or []:
        if isinstance(a,dict):articles.append({'title':a.get('title'),'source':a.get('source'),'published_at':a.get('published_at'),'symbols':a.get('symbols') or [],'news_score':a.get('news_score')})
    recent=[]
    if PUB.exists():
        for line in PUB.read_text(encoding='utf-8').splitlines()[-30:]:
            try:
                r=json.loads(line); recent.append({'hook':r.get('hook'),'symbol':r.get('symbol'),'topic':r.get('topic'),'published_at':r.get('published_at')})
            except Exception:pass
    move=float((item or {}).get('price_change_percent') or 0); volume=float((item or {}).get('quote_volume_usdt') or 0); price=float((item or {}).get('last_price') or 0)
    signal_score=float((item or {}).get('content_signal_score') or 0)
    related=[a for a in articles if symbol and any(sym(v)==symbol for v in (a.get('symbols') or []))]
    title=(related[0].get('title') if related else selected.get('news_title'))
    same_topic=[r for r in recent if sym(r.get('symbol'))==symbol]
    anomaly=[]
    if abs(move)>=8: anomaly.append('large_intraday_move')
    if float((item or {}).get('intraday_range_percent') or 0)>=20: anomaly.append('wide_intraday_range')
    if volume>=100000000: anomaly.append('high_quote_volume')
    if signal_score>=80: anomaly.append('high_content_signal')
    mechanisms=[]
    if abs(move)>=5 and volume>0: mechanisms.append('price_move_plus_volume_is_stronger_than_price_alone')
    if float((item or {}).get('intraday_range_percent') or 0)>abs(move)*1.5 and abs(move)>0: mechanisms.append('wide_range_exceeds_net_move_suggesting_intraday_two_way_activity')
    if related: mechanisms.append('news_asset_link_exists_but_news_does_not_by_itself_prove_price_causality')
    info_advantage=0
    info_advantage+=25 if anomaly else 0
    info_advantage+=20 if mechanisms else 0
    info_advantage+=15 if related else 0
    info_advantage+=15 if selected else 0
    info_advantage+=15 if not same_topic else 0
    info_advantage+=10 if item else 0
    thesis=(f"{symbol} is interesting because the live market evidence shows a measurable move/structure ({move:.2f}% price change, {volume:.0f} USDT quote volume) while the available context can be tested against the current narrative." if symbol else 'No authoritative asset available.')
    invalidation='The thesis should be rejected if the cited market relationship cannot be reproduced from the authoritative snapshot or if the news context does not support the claimed connection.'
    result={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'authoritative_market_item':item or {},'relevant_news':related[:5],'recent_same_symbol_publications':same_topic[-10:],'anomalies':anomaly,'derived_mechanisms':mechanisms,'thesis_seed':thesis,'invalidation':invalidation,'information_advantage_score':min(100,info_advantage),'research_status':'READY' if item else 'INSUFFICIENT_EVIDENCE','policy':['Facts come only from supplied snapshots.','Derived observations are labeled as derived.','News is not treated as proof of causality.','No invented targets, flows, whale activity, or trading outcomes.','Research can recommend WAIT when evidence is insufficient.']}
    OUT.parent.mkdir(parents=True,exist_ok=True);REPORT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');REPORT.write_text(json.dumps({'research':result,'decision':'RESEARCH_READY' if item else 'WAIT_FOR_EVIDENCE'},indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'1.0','symbol':symbol,'information_advantage_score':result['information_advantage_score'],'research_status':result['research_status']},indent=2))
if __name__=='__main__':main()
