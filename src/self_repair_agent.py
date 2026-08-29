"""Bounded autonomous software repair loop.

Detects failures, builds evidence-backed repair proposals, and keeps a memory
of what failed. The repair executor is deliberately gated: generated code is
not pushed straight to production. Any future executor must work in an isolated
copy, run tests, enforce a diff/file allowlist, and support rollback.
"""
from __future__ import annotations
import ast,json,subprocess,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/intelligence/self_repair_report.json'; QUEUE=ROOT/'data/intelligence/self_repair_queue.jsonl'; MEMORY=ROOT/'data/intelligence/self_repair_memory.jsonl'
MAX_FILES=3; MAX_DIFF_LINES=250

def run(cmd,timeout=120):
 try:
  p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
  return {'returncode':p.returncode,'stdout':p.stdout[-6000:],'stderr':p.stderr[-6000:]}
 except Exception as e:return {'returncode':99,'stdout':'','stderr':str(e)}

def collect():
 r={'generated_at':datetime.now(timezone.utc).isoformat(),'checks':{},'failures':[]}
 syntax=[]
 for f in (ROOT/'src').glob('*.py'):
  try:ast.parse(f.read_text(encoding='utf-8'),filename=str(f))
  except SyntaxError as e:syntax.append({'file':str(f.relative_to(ROOT)),'error':str(e)})
 r['checks']['python_syntax']=syntax
 r['checks']['compileall']=run(['python','-m','compileall','-q','src'])
 if r['checks']['compileall']['returncode']:r['failures'].append({'kind':'compileall','detail':r['checks']['compileall']['stderr']})
 r['failures'] += [{'kind':'syntax','detail':x} for x in syntax]
 for rel in ['data/live/creator_status.json','data/live/pipeline_state.json','data/live/production_manager.json']:
  p=ROOT/rel
  if p.exists():
   try:
    x=json.loads(p.read_text(encoding='utf-8'))
    if isinstance(x,dict) and str(x.get('status','')).lower() in {'error','failed'}:r['failures'].append({'kind':'pipeline_state','source':rel,'detail':x})
   except Exception:pass
 return r

def propose(f):
 detail=json.dumps(f,ensure_ascii=False)[:3000]; kind=f['kind']
 if kind in {'syntax','compileall'}: action='Fix only the reported syntax/import/compile defect; rerun compileall.'
 elif kind=='pipeline_state': action='Trace the recorded pipeline error to its producer/consumer contract; add a minimal backward-compatible fix.'
 else: action='Reproduce the failure from logs before changing code.'
 return {'failure':f,'repair_request':f'Diagnose from evidence only: {detail}. {action}','status':'PROPOSAL_ONLY','constraints':{'max_files':MAX_FILES,'max_diff_lines':MAX_DIFF_LINES,'must_pass_syntax':True,'must_not_touch_secrets':True,'must_not_modify_workflows_or_publishing_credentials_automatically':True}}

def main():
 report=collect(); proposals=[propose(f) for f in report['failures']]
 report['status']='HEALTHY_NO_REPAIR_REQUIRED' if not proposals else 'REPAIR_PROPOSALS_READY'; report['proposals']=proposals
 report['self_improvement_contract']={'observe':True,'diagnose':True,'propose':True,'isolated_patch_required':True,'tests_required':True,'rollback_required':True,'direct_production_push':False}
 report['deployment_policy']='AI may generate a candidate patch only in an isolated workspace/branch. It must pass tests, diff/file limits and a controlled repository gate before merge. Secrets and publishing credentials are never modified by this agent.'
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 if proposals:
  with QUEUE.open('a',encoding='utf-8') as f:
   for p in proposals:f.write(json.dumps(p,ensure_ascii=False)+'\n')
 with MEMORY.open('a',encoding='utf-8') as f:f.write(json.dumps({'at':report['generated_at'],'status':report['status'],'failures':len(report['failures'])},ensure_ascii=False)+'\n')
 print(json.dumps({'status':report['status'],'failures':len(report['failures']),'proposals':len(proposals)}))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'SELF_REPAIR_AGENT_ERROR','error':str(e),'traceback':traceback.format_exc()}));raise
