"""Persist verified repair outcomes as reusable engineering memory."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MEM=ROOT/'data/intelligence/repair_memory.jsonl'
REPORT=ROOT/'data/intelligence/repair_sandbox_report.json'
QUEUE=ROOT/'data/intelligence/self_repair_queue.jsonl'
def main():
 try:r=json.loads(REPORT.read_text(encoding='utf-8'))
 except Exception:r={}
 if r.get('status')!='PASSED_ISOLATED_TESTS': print(json.dumps({'status':'NOT_RECORDED'})); return
 entry={'recorded_at':datetime.now(timezone.utc).isoformat(),'fingerprint':hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()[:16],'sandbox_status':r.get('status'),'deployment':r.get('deployment'),'rule':'verified in isolated sandbox; review required before production'}
 MEM.parent.mkdir(parents=True,exist_ok=True)
 with MEM.open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
 print(json.dumps({'status':'RECORDED','fingerprint':entry['fingerprint']}))
if __name__=='__main__':main()
