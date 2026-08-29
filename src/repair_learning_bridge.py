"""Feed verified engineering outcomes back into Living Brain memory.

It converts repair evidence into recurring architectural observations and
bounded next actions. It does not deploy code or change production itself.
"""
from __future__ import annotations
import json, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'data/intelligence/repair_sandbox_report.json'
QUEUE=ROOT/'data/intelligence/self_repair_queue.jsonl'
MEM=ROOT/'data/intelligence/repair_learning.json'
BRAIN=ROOT/'data/intelligence/living_brain.json'

def read(p,default):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return default

def main():
 report=read(REPORT,{})
 history=[]
 if QUEUE.exists():
  for line in QUEUE.read_text(encoding='utf-8').splitlines():
   try: history.append(json.loads(line))
   except Exception: pass
 previous=read(MEM,{'events':[]})
 events=previous.get('events',[]) if isinstance(previous,dict) else []
 status=report.get('status','UNKNOWN')
 event={'at':datetime.now(timezone.utc).isoformat(),'sandbox_status':status,'tests':report.get('tests',[]),'deployment':report.get('deployment','blocked')}
 if status in ('PASSED_ISOLATED_TESTS','REJECTED_TEST_FAILURE','REJECTED'): events.append(event)
 events=events[-200:]
 counts=Counter(x.get('sandbox_status','UNKNOWN') for x in events)
 recurring=[]
 if counts.get('REJECTED_TEST_FAILURE',0)>=3: recurring.append({'severity':'HIGH','issue':'repair candidates repeatedly fail tests','action':'Improve test coverage and require smaller patches before another repair attempt.'})
 if counts.get('REJECTED',0)>=3: recurring.append({'severity':'MEDIUM','issue':'repair candidates repeatedly violate patch policy','action':'Tighten coding-agent instructions and forbidden-path validation.'})
 if len(history)>=5: recurring.append({'severity':'MEDIUM','issue':'repair queue has accumulated multiple events','action':'Prioritize root-cause work over repeated symptom patches.'})
 brain=read(BRAIN,{})
 current=brain.get('system_health',{}) if isinstance(brain,dict) else {}
 out={'updated_at':event['at'],'events':events,'summary':{'total_recorded':len(events),'status_counts':dict(counts)},'recurring_architectural_risks':recurring,'brain_feedback':{'merge_into_next_cycle':True,'add_priorities':recurring,'principle':'Prefer fixing recurring root causes and missing tests over repeatedly patching symptoms.'},'fingerprint':hashlib.sha256(json.dumps(events,sort_keys=True).encode()).hexdigest()[:16]}
 MEM.parent.mkdir(parents=True,exist_ok=True);MEM.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
 # Patch the current brain snapshot without inventing unrelated metrics.
 if brain:
  brain['repair_learning']= {'summary':out['summary'],'recurring_architectural_risks':recurring,'updated_at':event['at']}
  BRAIN.write_text(json.dumps(brain,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','recorded':len(events),'recurring_risks':len(recurring)}))
if __name__=='__main__':main()
