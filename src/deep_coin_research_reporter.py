"""Deep Coin Research Reporter 1.0.
Turns the screening output into explicit, auditable research dossiers.
It does not invent missing fundamentals: unknown stays unknown.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/live/original_research.json'; NEWS=ROOT/'data/live/news_snapshot.json'; OUT=ROOT/'data/intelligence/deep_coin_research_report.json'; DOS=ROOT/'data/intelligence/coin_dossiers'

def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return {}
def main():
 src=load(SRC); news=load(NEWS); articles=news.get('articles') or []; now=datetime.now(timezone.utc).isoformat(); DOS.mkdir(parents=True,exist_ok=True)
 queue=src.get('research_queue') or [x.get('symbol') for x in src.get('potential_gems',[])[:8]]
 by={}
 for x in (src.get('potential_gems',[])+src.get('potential_risks',[])):
  by[x.get('symbol')]=x
 reports=[]
 for s in queue[:10]:
  x=by.get(s,{})
  rel=[a for a in articles if s and (s in [str(v).upper().replace('USDT','') for v in a.get('symbols') or []] or s in (str(a.get('title',''))+' '+str(a.get('summary',''))).upper())]
  dossier={'symbol':s,'generated_at':now,'status':'SCREENED_NOT_FULLY_VERIFIED','thesis':{'statement':f'{s} merits deeper investigation based on current market/news signals.','type':'HYPOTHESIS','confidence':'LOW_TO_MEDIUM'},'evidence':{'market_observations':{'move_pct':x.get('move_pct'),'volume_usdt':x.get('quote_volume_usdt'),'range_pct':x.get('range_pct'),'anomaly_score':x.get('market_anomaly_score')},'news':[{ 'title':a.get('title'),'source':a.get('source'),'category':a.get('category')} for a in rel[:8]]},'100x_audit':x.get('100x_feasibility',{}),'survival_audit':{'risk_score':x.get('risk_red_flag_score'),'status':'REQUIRES_PRIMARY_VERIFICATION','checks':x.get('research_questions',[])},'scenarios':x.get('scenario',{}),'undercoverage_score':x.get('undercoverage_score'),'missing_evidence':x.get('missing_evidence',[]),'killer_questions':['What evidence would make this thesis wrong?','What independent source could corroborate the key claim?','What would have to change for the 100x scenario to become economically plausible?','What would constitute a genuine survival/failure warning?'],'publication_guidance':'Do not publish a certainty claim from this dossier. Publish only verified findings, clearly label interpretation/hypothesis, and prefer a useful research insight over a price prediction.'}
  (DOS/f'{s.lower()}.json').write_text(json.dumps(dossier,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); reports.append(dossier)
 result={'version':'1.0','generated_at':now,'status':'READY_FOR_EDITORIAL_SELECTION' if reports else 'NO_RESEARCH','dossier_count':len(reports),'dossiers':reports,'policy':'100x and failure scenarios are analytical tests, not promises. Unknown data is never filled with guesses.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps({'status':result['status'],'dossier_count':len(reports),'symbols':[r['symbol'] for r in reports]},indent=2))
if __name__=='__main__':main()
