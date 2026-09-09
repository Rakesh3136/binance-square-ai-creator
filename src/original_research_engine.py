"""Original Research Engine 3.1 — asymmetric crypto intelligence.

Pre-screens the live universe for undercovered opportunities and structural risk,
then quantifies scenario feasibility without pretending forecasts are facts.
Every material conclusion carries an epistemic status and explicit missing-data list.
"""
from __future__ import annotations
import json, math, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/'data/live/market_snapshot.json'; NEWS=ROOT/'data/live/news_snapshot.json'; PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; PUB=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/original_research.json'; REPORT=ROOT/'data/intelligence/original_research_report.json'; LEDGER=ROOT/'data/intelligence/thesis_ledger.jsonl'

def load(p):
 try:
  x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
 except Exception:return {}
def sym(v): return re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())
def n(v):
 try:return float(v)
 except:return 0.0
def clamp(x): return round(max(0,min(100,x)),2)
def first_num(x,*keys):
 for k in keys:
  if isinstance(x,dict) and x.get(k) not in (None,''): return n(x[k])
 return 0.0
def rows(m):
 out=[];seen=set()
 for g in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
  for x in m.get(g) or []:
   if not isinstance(x,dict):continue
   s=sym(x.get('symbol'))
   if s and s not in seen and x.get('last_price') is not None:seen.add(s);out.append(x)
 return out[:200]
def main():
 m=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT); articles=[a for a in news.get('articles') or [] if isinstance(a,dict)]; pubs=[]
 if PUB.exists():
  for line in PUB.read_text(encoding='utf-8').splitlines()[-200:]:
   try: pubs.append(json.loads(line))
   except: pass
 results=[]
 risk_words=('hack','exploit','lawsuit','delist','delisting','insolven','bankrupt','bankruptcy','unlock','rug','investigation','fraud','breach','halt','vulnerability','drain','attack')
 for x in rows(m):
  s=sym(x.get('symbol')); move=n(x.get('price_change_percent')); vol=first_num(x,'quote_volume_usdt','quote_volume'); rng=n(x.get('intraday_range_percent')); signal=n(x.get('content_signal_score'))
  price=n(x.get('last_price')); mcap=first_num(x,'market_cap','market_cap_usdt','marketCap'); fdv=first_num(x,'fdv','fully_diluted_valuation','fully_diluted_market_cap'); circ=first_num(x,'circulating_supply','circulatingSupply'); supply=first_num(x,'max_supply','total_supply','totalSupply')
  rel=[a for a in articles if s and (s in [sym(v) for v in a.get('symbols') or []] or re.search(r'\b'+re.escape(s.lower())+r'\b',(str(a.get('title',''))+' '+str(a.get('summary',''))).lower()))]
  official=sum(1 for a in rel if str(a.get('category','')).endswith('_official')); risk_hits=sum(1 for a in rel if any(w in (str(a.get('title',''))+' '+str(a.get('summary',''))).lower() for w in risk_words))
  evidence=clamp(30+min(40,len(rel)*8)+min(30,official*15)); liquidity=clamp(math.log10(max(vol,1))*12); anomaly=clamp(45+abs(move)*1.3+min(20,rng*.2)+signal*.2); risk=clamp(risk_hits*20+(25 if liquidity<45 else 0)+(15 if rng>60 else 0)); upside=clamp(25+anomaly*.35+evidence*.3+liquidity*.2-risk*.4)
  prior=sum(1 for p in pubs if sym(p.get('symbol'))==s); coverage=len(rel)+prior
  undercovered=clamp(100-coverage*12)
  # Information advantage measures how much differentiated research signal exists here:
  # undercoverage + evidence + market anomaly. This is a research-derived signal, not a claim of certainty.
  information_advantage=clamp(undercovered*.45 + evidence*.30 + anomaly*.25)
  mcap_base=mcap or (fdv*(circ/supply) if fdv and circ and supply else 0)
  implied_100x=mcap_base*100 if mcap_base else 0
  dilution=clamp((1-(mcap_base/fdv))*100) if fdv and mcap_base else None
  feasibility=clamp(55 + min(25,math.log10(max(1,mcap_base))*2) - (dilution or 0)*.35 - risk*.25 + min(20,evidence*.2)) if mcap_base else None
  missing=[]
  for label,val in [('market_cap',mcap_base),('fdv',fdv),('circulating_supply',circ),('product_adoption',0),('revenue_or_fees',0),('holder_concentration',0),('unlocks',0),('security_audits',0)]:
   if not val: missing.append(label)
  bull=clamp(upside+15); base=clamp(upside); bear=clamp(risk+20)
  if bull>70 and bear>65: regime='ASYMMETRIC_BUT_HIGH_RISK'
  elif bull>70: regime='UPSIDE_WATCH'
  elif bear>65: regime='SURVIVAL_RISK_WATCH'
  else: regime='MONITOR'
  results.append({'symbol':s,'price':price,'move_pct':move,'quote_volume_usdt':vol,'range_pct':rng,'content_signal_score':signal,'news_count':len(rel),'official_evidence_count':official,'prior_publications':prior,'undercoverage_score':undercovered,'evidence_score':evidence,'liquidity_score':liquidity,'market_anomaly_score':anomaly,'information_advantage_score':information_advantage,'risk_red_flag_score':risk,'upside_optionality_score':upside,'scenario':{'bull_score':bull,'base_score':base,'bear_risk_score':bear,'regime':regime},'100x_feasibility':{'current_market_cap':mcap_base,'implied_market_cap_100x':implied_100x,'fdv':fdv,'dilution_pressure_pct':dilution,'feasibility_score':feasibility,'status':'CALCULABLE' if mcap_base else 'INSUFFICIENT_MARKET_CAP_DATA'},'research_questions':['What fundamental product/use creates durable demand?','What are circulating supply, FDV and unlock schedules?','How concentrated are holders and liquidity?','What measurable adoption, revenue or fees exist?','What security, governance, legal or treasury risks exist?','Which catalysts are confirmed by primary sources?','What evidence would invalidate the upside thesis?','What evidence would indicate structural failure?'],'missing_evidence':missing,'epistemic_note':'Market/news signals are observations; upside and failure scores are screening heuristics, not predictions.'})
 gems=sorted(results,key=lambda r:(r['upside_optionality_score'],r['undercoverage_score'],r['evidence_score']),reverse=True)[:12]; risks=sorted(results,key=lambda r:(r['risk_red_flag_score'],r['bear_risk_score'] if 'bear_risk_score' in r else 0),reverse=True)[:12]
 selected=pre.get('selected_opportunity') or {}; selected_sym=sym(selected.get('symbol'))
 info_advantage=max((r['information_advantage_score'] for r in results),default=None)
 selected_info_advantage=next((r['information_advantage_score'] for r in results if r.get('symbol')==selected_sym),info_advantage)
 state={'version':'3.1','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY_FOR_DEEP_RESEARCH' if results else 'NO_CANDIDATES','universe_size':len(results),'method':'market anomaly + evidence + liquidity + risk + undercoverage + scenario feasibility','information_advantage_score':selected_info_advantage,'information_advantage_method':'weighted undercoverage(45%) + evidence(30%) + market anomaly(25%); research signal, not certainty','potential_gems':gems,'potential_risks':risks,'selected_story_symbol':selected_sym,'research_queue':[r['symbol'] for r in gems[:8]],'required_deep_checks':['primary project documentation','tokenomics and unlocks','holder concentration','product usage/adoption','treasury/runway if disclosed','security/audits/incidents','developer/governance activity','confirmed catalysts','comparable valuation','failure/invalidation scenarios'],'epistemic_labels':['VERIFIED_FACT','DERIVED_OBSERVATION','INTERPRETATION','HYPOTHESIS','UNKNOWN'],'publication_policy':'Investigate 100x and failure scenarios without manufacturing certainty. Never state a coin will 100x or go bankrupt unless a source literally establishes the fact; normally use feasibility/risk language, disclose uncertainty, and require corroboration.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); REPORT.write_text(json.dumps({'module':'original_research_engine','version':'3.1','generated_at':state['generated_at'],'information_advantage_score':selected_info_advantage,'top_gems':[r['symbol'] for r in gems],'top_risks':[r['symbol'] for r in risks],'research_queue':state['research_queue'],'universe_size':len(results)},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps({'status':state['status'],'version':'3.1','universe_size':len(results),'information_advantage_score':selected_info_advantage,'potential_gems':[r['symbol'] for r in gems[:5]],'potential_risks':[r['symbol'] for r in risks[:5]],'research_queue':state['research_queue']},indent=2))
if __name__=='__main__': main()
