"""Expandable engineering knowledge layer.

Maintains a local, versioned knowledge registry and turns repair outcomes into
reusable engineering lessons. External documentation ingestion can be added via
approved sources; this module never executes retrieved code as trusted code.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MEM=ROOT/'data/intelligence/engineering_knowledge.jsonl'
REPAIRS=ROOT/'data/intelligence/repair_memory.jsonl'
OUT=ROOT/'data/intelligence/knowledge_digest.json'
SEED=[
 {'domain':'python','principles':['small functions','explicit errors','type-aware data validation','deterministic tests']},
 {'domain':'apis','principles':['timeouts','retries with backoff','schema validation','idempotency','rate-limit handling']},
 {'domain':'github_actions','principles':['least privilege','pinned/reviewed actions','artifact logs','failure gates','rollback']},
 {'domain':'ai_engineering','principles':['structured outputs','evidence-first prompts','bounded autonomy','evaluation before deployment']},
 {'domain':'software_reliability','principles':['observability','health checks','regression tests','immutable audit records']},
]
def main():
 MEM.parent.mkdir(parents=True,exist_ok=True)
 existing=[]
 if MEM.exists():
  for line in MEM.read_text(encoding='utf-8').splitlines():
   try: existing.append(json.loads(line))
   except: pass
 known={x.get('id') for x in existing}
 now=datetime.now(timezone.utc).isoformat()
 for item in SEED:
  item=dict(item); item['id']=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:16];item['updated_at']=now
  if item['id'] not in known:
   with MEM.open('a',encoding='utf-8') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
 repair_count=sum(1 for _ in REPAIRS.open(encoding='utf-8')) if REPAIRS.exists() else 0
 digest={'generated_at':now,'knowledge_entries':len(existing)+sum(1 for x in SEED if x['id'] not in known),'repair_lessons':repair_count,'domains':sorted({x.get('domain','unknown') for x in existing+SEED}),'policy':'Knowledge is evidence and guidance; retrieved code is untrusted until reviewed and tested.'}
 OUT.write_text(json.dumps(digest,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(digest))
if __name__=='__main__':main()
