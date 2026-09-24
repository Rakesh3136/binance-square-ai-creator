"""Global Macro Intelligence: event -> cross-asset context -> crypto implications.

This layer is evidence-first. It does not invent market prices, declare an asset
'safest', or create trade levels. It classifies verified news already collected by
the creator and turns it into a bounded macro context that downstream routing can
use alongside live market evidence.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NEWS=ROOT/'data/live/news_snapshot.json'
MARKET=ROOT/'data/live/market_snapshot.json'
OUT=ROOT/'data/live/global_macro_intelligence.json'
REPORT=ROOT/'data/intelligence/global_macro_intelligence_report.json'

THEMES={
 'geopolitical_risk':('war','warfare','conflict','missile','strike','invasion','military','ceasefire','sanction','sanctions','blockade','red sea','shipping'),
 'energy_shock':('oil','crude','brent','wti','gas','lng','opec','energy'),
 'monetary_policy':('fed','federal reserve','ecb','boj','central bank','interest rate','rate cut','rate hike','powell'),
 'inflation':('inflation','cpi','ppi','prices','consumer price'),
 'growth_risk':('recession','slowdown','unemployment','jobs','gdp','default','credit stress'),
 'trade_policy':('tariff','tariffs','trade war','export control','import ban'),
 'commodities':('gold','silver','copper','commodity','commodities'),
 'regulation':('sec','regulation','regulatory','law','legislation','stablecoin')}

def load(p):
 try:
  x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
 except Exception:return {}
def classify(text):
 t=str(text or '').lower(); hits=[]
 for k,words in THEMES.items():
  n=sum(1 for w in words if w in t)
  if n:hits.append((k,n))
 return sorted(hits,key=lambda x:x[1],reverse=True)
def main():
 news,market=load(NEWS),load(MARKET); articles=news.get('articles') if isinstance(news.get('articles'),list) else []
 events=[]
 for a in articles:
  title=str(a.get('title') or '').strip(); desc=str(a.get('description') or a.get('summary') or '')
  themes=classify(title+' '+desc)
  if not title or not themes: continue
  top,n=themes[0]
  if n<1: continue
  events.append({'title':title[:280],'source':str(a.get('source') or ''),'url':str(a.get('url') or ''),'published_at':str(a.get('published_at') or ''),'themes':[x[0] for x in themes[:4]],'primary_theme':top,'asset_symbols':[str(x).upper() for x in (a.get('symbols') or []) if re.fullmatch(r'[A-Za-z0-9:_-]{2,30}',str(x))][:8]})
 events=events[:40]
 counts={k:0 for k in THEMES}
 for e in events:
  for k in e['themes']:counts[k]+=1
 active=sorted(((k,v) for k,v in counts.items() if v),key=lambda x:x[1],reverse=True)
 primary=active[0][0] if active else 'none'
 # Cross-asset implications are hypotheses, never price predictions.
 mapping={
  'geopolitical_risk':['gold','usd','oil','rates','btc/crypto risk appetite'],
  'energy_shock':['oil','inflation expectations','rates','risk assets','crypto liquidity'],
  'monetary_policy':['usd','treasuries/yields','gold','equities','btc/crypto liquidity'],
  'inflation':['gold','rates','usd','risk assets','crypto liquidity'],
  'growth_risk':['treasuries/yields','usd','equities','commodities','crypto risk appetite'],
  'trade_policy':['commodities','usd','equities','inflation expectations','crypto risk appetite'],
  'commodities':['gold','silver','oil','copper','crypto risk appetite'],
  'regulation':['stablecoins','btc','eth','exchange-listed assets']}
 result={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY' if events else 'NO_MACRO_EVENT','primary_theme':primary,'event_count':len(events),'theme_counts':counts,'cross_asset_watchlist':mapping.get(primary,[]),'event_to_crypto_framework':['verify event','measure cross-asset reaction','measure crypto relative strength/capital flow','only then consider a conditional crypto setup'],'defensive_asset_policy':'Do not label any asset universally safest. Compare resilience/volatility/liquidity using current evidence.','prediction_policy':'Macro events create context, not automatic coin predictions. A LONG/SHORT requires the existing verified signal contract.','events':events}
 OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); REPORT.write_text(json.dumps({'version':'1.0','status':result['status'],'event_count':len(events),'primary_theme':primary},indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':result['status'],'primary_theme':primary,'event_count':len(events)}))
if __name__=='__main__':main()
