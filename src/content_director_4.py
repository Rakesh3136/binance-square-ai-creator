"""Binance Square Creator 4.0 content director.
Ranks *story opportunities*, not just coins, before the writing model runs.
It uses only local verified snapshots and never pretends to know a hidden platform algorithm.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/content_director_brief.json'
LANES={
 'breaking_news':24,'news_market_impact':22,'technical_breakout':20,'top_mover':15,'volume_anomaly':18,
 'liquidation':18,'new_listing':21,'macro':22,'creator_signal_outcome':20,'education':10,'comparison':13,'follow_up':17}

def load(p):
 try:
  x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
 except Exception:return {}
def num(x):
 try:return float(x)
 except:return 0.0
def text(x): return str(x or '').strip()
def symbol(x):
 s=text(x).upper().replace('$',''); return s[:-4] if s.endswith('USDT') else s
def news_score(a):
 t=(text(a.get('title'))+' '+text(a.get('summary'))+' '+text(a.get('description'))).lower(); score=0
 for k,w in [('breaking',12),('hack',16),('exploit',16),('etf',13),('sec',10),('fed',10),('rate',8),('inflation',8),('listing',12),('upgrade',8),('partnership',6),('regulation',9),('liquidation',10),('whale',9)]:
  if k in t: score+=w
 return score

def main():
 market=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT)
 stories=[]
 for lane,groups in [('top_mover',['top_gainers','top_losers']),('volume_anomaly',['highest_volume']),('technical_breakout',['top_content_signals']),('new_listing',['new_listing_market'])]:
  for g in groups:
   for x in market.get(g) or []:
    if not isinstance(x,dict) or not x.get('symbol'): continue
    move=abs(num(x.get('price_change_percent'))); vol=num(x.get('quote_volume_usdt') or x.get('quote_volume')); signal=num(x.get('content_signal_score'))
    score=LANES[lane]+min(28,move*0.45)+min(16,signal*0.16)+min(10,vol/1e8)
    stories.append({'lane':lane,'symbol':symbol(x['symbol']),'score':round(score,2),'price_change_percent':num(x.get('price_change_percent')),'quote_volume_usdt':vol,'content_signal_score':signal,'reason':'large verified market move/attention signal'})
 for a in (news.get('articles') or news.get('items') or []):
  if not isinstance(a,dict): continue
  ns=news_score(a)
  if ns<=0: continue
  title=text(a.get('title'))[:180]
  stories.append({'lane':'breaking_news' if ns>=16 else 'news_market_impact','score':round(LANES['breaking_news']+ns,2),'title':title,'url':text(a.get('url') or a.get('link')),'reason':'fresh news contains a material crypto catalyst'})
 stories.sort(key=lambda x:x['score'],reverse=True)
 recent=pre.get('engagement_strategy') or {}; recent_styles=recent.get('recent_style_counts') or {}
 top=stories[0] if stories else {'lane':'education','score':10,'reason':'No material catalyst passed the evidence threshold; use an educational live-chart story.'}
 lane=top['lane']
 format_map={'breaking_news':'BREAKING NEWS + MARKET IMPACT','news_market_impact':'NEWS + CHART','technical_breakout':'TRADINGVIEW CHART CHALLENGE','top_mover':'TOP MOVERS','volume_anomaly':'DATA SURPRISE','liquidation':'LIQUIDATION STORY','new_listing':'NEW LISTING WATCH','macro':'MACRO + MARKET IMPACT','creator_signal_outcome':'CREATOR CALL OUTCOME','education':'EDUCATION FROM LIVE CHART','comparison':'COIN VS COIN','follow_up':'FOLLOW-UP / UPDATE'}
 brief={'generated_at':datetime.now(timezone.utc).isoformat(),'director_version':'4.0','algorithm_policy':'Treat observed engagement patterns as experiments, never as knowledge of a hidden recommendation algorithm. Optimize for genuine attention, useful interaction, follower conversion and eligible monetization.','primary_story':top,'recommended_format':format_map.get(lane,'NEWS + CHART'),'coverage_mix':['breaking_news','macro','technical_breakout','top_mover','volume_anomaly','new_listing','liquidation','creator_signal_outcome','education','comparison','follow_up'],'story_rules':['Prefer a concrete catalyst or surprising data point over generic price recap.','Explain why the story matters now.','Use one primary asset when a chart can prove the thesis.','Use verified current data and synchronized TradingView visual for technical stories.','End with one easy interaction question.','Do not copy creators or fabricate claims.','Do not promise 10x/20x outcomes; frame upside as scenarios.'],'recent_style_counts':recent_styles,'ranked_stories':stories[:25]}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
 pre['content_director_4']=brief
 pre['content_director_instruction']=f"Creator 4.0 selected {brief['recommended_format']}. Lead with the strongest verified reason: {top.get('reason','verified opportunity')}. Do not default to a generic market recap."
 PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','director':'4.0','lane':lane,'format':brief['recommended_format'],'top_score':top.get('score')},indent=2))
if __name__=='__main__': main()
