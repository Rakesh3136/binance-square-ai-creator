"""Orchestrate bounded diagnose -> patch -> sandbox -> iterate loop.

Iteration is capped. A passing patch is marked review-ready; failures become
feedback for the next attempt. This module never merges or deploys changes.
"""
from __future__ import annotations
import json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/'data/intelligence/ai_code_patch.json'
REPORT=ROOT/'data/intelligence/repair_sandbox_report.json'

def read(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return {}

def main():
 max_rounds=min(int(os.getenv('REPAIR_MAX_ROUNDS','2')),3)
 history=[]
 for n in range(1,max_rounds+1):
  r=read(PATCH)
  if r.get('status')!='PATCH_READY': history.append({'round':n,'status':'NO_PATCH'}); break
  env=os.environ.copy();env['REPAIR_PATCH']=r['patch']
  p=subprocess.run(['python','src/repair_sandbox.py'],cwd=ROOT,text=True,capture_output=True,env=env)
  outcome=read(REPORT); history.append({'round':n,'sandbox_status':outcome.get('status'),'stdout':p.stdout[-2000:],'stderr':p.stderr[-2000:]})
  if outcome.get('status')=='PASSED_ISOLATED_TESTS':
   subprocess.run(['python','src/repair_memory.py'],cwd=ROOT,check=False);break
  # A failed candidate is never applied to the working tree. A future round
  # must regenerate a fresh candidate using updated failure evidence.
  PATCH.unlink(missing_ok=True)
 result={'status':'REVIEW_READY' if history and history[-1].get('sandbox_status')=='PASSED_ISOLATED_TESTS' else 'BLOCKED','rounds':history,'deployment':'never_automatic'}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
