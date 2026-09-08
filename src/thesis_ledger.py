"""Persistent thesis ledger with explicit hypothesis/outcome separation."""
from pathlib import Path
import json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; RESEARCH=ROOT/'data/intelligence/deep_coin_research_report.json'; OUT=ROOT/'data/intelligence/thesis_ledger.json'
def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return {}
def main():
 d=load(OUT); d.setdefault('version',2); d.setdefault('theses',[]); d['last_updated']=datetime.now(timezone.utc).isoformat(); r=load(RESEARCH)
 existing={x.get('thesis_id') for x in d['theses']}; added=0
 for q in r.get('dossiers',[]):
  s=q.get('symbol',''); statement=q.get('thesis',{}).get('statement',''); tid=f'{s}:{statement}'
  if tid in existing: continue
  d['theses'].append({'thesis_id':tid,'symbol':s,'created_at':datetime.now(timezone.utc).isoformat(),'status':'ACTIVE_HYPOTHESIS','thesis':statement,'confidence':q.get('thesis',{}).get('confidence'),'evidence_snapshot':q.get('evidence',{}),'100x_audit':q.get('100x_audit',{}),'survival_audit':q.get('survival_audit',{}),'scenarios':q.get('scenarios',{}),'missing_evidence':q.get('missing_evidence',[]),'killer_questions':q.get('killer_questions',[]),'outcome':None}); added+=1
 d['rules']=['Never convert a hypothesis into a fact.','Store evidence snapshots separately from later outcomes.','Revisit unresolved theses when new verified evidence appears.','Mark theses CONFIRMED, WEAKENED or INVALIDATED only from subsequent evidence.']
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n'); print(json.dumps({'status':'OK','new_theses':added,'total_theses':len(d['theses'])},indent=2))
if __name__=='__main__':main()
