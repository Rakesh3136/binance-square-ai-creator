"""Original Research Engine 2.0 — deep coin due diligence.
Builds evidence-led research candidates across the live market and news universe.
It identifies potential asymmetric upside AND failure risk; it never predicts a
certain 100x return or bankruptcy. Claims require evidence and primary verification.
"""
from __future__ import annotations
import json,math,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUB=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/original_research.json'; REPORT=ROOT/'data/intelligence/original_research_report.json'
def load(p):
 try:
  x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
 except Exception:return {}
def sym(v):return re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())
def n(v):
 try:return float(v)
 except:return 0.0
def clamp(x):return round(max(0,min(100,x)),2)
def rows(m):
 out=[];seen=set()
 for g in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
  for x in m.get(g) or []:
   if not isinstance(x,dict):continue
   s=sym(x.get('symbol'))
   if s and s not in seen and x.get('last_price') is not None:seen.add(s);out.append(x)
 return out[:150]
def main():
 m=load(MARKET);news=load(NEWS);pre=load(PREFLIGHT); articles=[a for a in news.get('articles') or [] if isinstance(a,dict)]; pubs=[]
 if PUB.exists():
  for line in PUB.read_text(encoding='utf-8').splitlines()[-80:]:
   try:pubs.append(json.loads(line))
   except:pass
 results=[]
 risk_words=('hack','exploit','lawsuit','delist','delisting','insolven','bankrupt','bankruptcy','unlock','rug','investigation','fraud','breach','halt','vulnerability')
 for x in rows(m):
  s=sym(x.get('symbol')); move=n(x.get('price_change_percent'));vol=n(x.get('quote_volume_usdt') or x.get('quote_volume'));rng=n(x.get('intraday_range_percent'));signal=n(x.get('content_signal_score'))
  rel=[a for a in articles if s and (s in [sym(v) for v in a.get('symbols') or []] or re.search(r'\b'+re.escape(s.lower())+r'\b',(str(a.get('title',''))+' '+str(a.get('summary',''))).lower()))]
  official=sum(1 for a in rel if str(a.get('category','')).endswith('_official'));risk_hits=sum(1 for a in rel if any(w in (str(a.get('title',''))+' '+str(a.get('summary',''))).lower() for w in risk_words))
  evidence=clamp(30+min(40,len(rel)*8)+min(30,official*15)); liquidity=clamp(math.log10(max(vol,1))*12); anomaly=clamp(45+abs(move)*1.3+min(20,rng*.2)+signal*.2)
  risk=clamp(risk_hits*20+(25 if liquidity<45 else 0)+(15 if rng>60 else 0)); upside=clamp(25+anomaly*.35+evidence*.3+liquidity*.2-risk*.4)
  prior=sum(1 for p in pubs if sym(p.get('symbol'))==s)
  results.append({'symbol':s,'price':n(x.get('last_price')),'move_pct':move,'quote_volume_usdt':vol,'range_pct':rng,'content_signal_score':signal,'news_count':len(rel),'official_evidence_count':official,'evidence_score':evidence,'liquidity_score':liquidity,'market_anomaly_score':anomaly,'risk_red_flag_score':risk,'upside_optionality_score':upside,'prior_publications':prior,'research_questions':['What fundamental product/use is creating demand?','What is the circulating supply versus fully diluted supply?','What unlocks/concentration could pressure holders?','What measurable adoption or revenue evidence exists?','What security/governance failures could break the thesis?','What catalyst is actually confirmed by a primary source?','What evidence would invalidate the upside thesis?','What evidence would indicate structural failure or insolvency risk?']})
 gems=sorted(results,key=lambda r:(r['upside_optionality_score'],r['evidence_score']),reverse=True)[:10]; risks=sorted(results,key=lambda r:(r['risk_red_flag_score'],r['market_anomaly_score']),reverse=True)[:10]
 selected=pre.get('selected_opportunity') or {}; selected_sym=sym(selected.get('symbol'))
 state={'version':'2.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY_FOR_DEEP_RESEARCH' if results else 'NO_CANDIDATES','universe_size':len(results),'method':'market anomaly + evidence + liquidity + explicit risk signals; not a return predictor','potential_gems':gems,'potential_risks':risks,'selected_story_symbol':selected_sym,'required_deep_checks':['primary project documentation','tokenomics and unlocks','holder concentration','product usage/adoption','treasury/runway if disclosed','security/audits/incidents','developer/governance activity','confirmed catalysts','comparable valuation','failure/invalidation scenarios'],'epistemic_labels':['VERIFIED_FACT','DERIVED_OBSERVATION','INTERPRETATION','HYPOTHESIS','UNKNOWN'],'publication_policy':'Never state that a coin will 100x or go bankrupt. Use evidence-backed asymmetric-upside or failure-risk language, disclose uncertainty, and require primary verification for material claims.'}
 OUT.parent.mkdir(parents=True,exist_ok=True);REPORT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');REPORT.write_text(json.dumps({'module':'original_research_engine','generated_at':state['generated_at'],'top_gems':[r['symbol'] for r in gems],'top_risks':[r['symbol'] for r in risks],'universe_size':len(results)},indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps({'status':state['status'],'universe_size':len(results),'potential_gems':[r['symbol'] for r in gems[:5]],'potential_risks':[r['symbol'] for r in risks[:5]]},indent=2))
if __name__=='__main__':main()
