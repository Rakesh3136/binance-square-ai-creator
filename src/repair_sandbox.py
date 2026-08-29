"""Isolated patch evaluator for self-repair proposals.

Copies the repository into a temporary directory, applies a bounded unified diff,
then runs syntax/compile checks and the repository's test suite if present.
Nothing is pushed or deployed by this module.
"""
from __future__ import annotations
import json, os, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/intelligence/repair_sandbox_report.json'
MAX_DIFF=250

def run(cmd,cwd,timeout=180):
 p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return {'returncode':p.returncode,'stdout':p.stdout[-5000:],'stderr':p.stderr[-5000:]}

def apply_patch(root, patch):
 p=root/'repair.patch'; p.write_text(patch,encoding='utf-8')
 lines=patch.splitlines()
 if len(lines)>MAX_DIFF: raise ValueError('patch exceeds maximum diff size')
 r=run(['git','apply','--check',str(p)],root,30)
 if r['returncode']!=0: raise ValueError('git apply --check failed: '+r['stderr'])
 r=run(['git','apply','--index',str(p)],root,30)
 if r['returncode']!=0: raise ValueError('git apply failed: '+r['stderr'])
 p.unlink(missing_ok=True)

def main():
 patch=os.environ.get('REPAIR_PATCH','')
 report={'generated_at':datetime.now(timezone.utc).isoformat(),'status':'NO_PATCH','tests':[]}
 if not patch.strip():
  OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));return
 with tempfile.TemporaryDirectory(prefix='repair-sandbox-') as td:
  sandbox=Path(td)/'repo'; shutil.copytree(ROOT,sandbox,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
  try: apply_patch(sandbox,patch)
  except Exception as e:
   report.update(status='REJECTED',error=str(e));
  else:
   report['tests'].append({'name':'python_compileall','result':run(['python','-m','compileall','-q','src'],sandbox)})
   if (sandbox/'tests').exists(): report['tests'].append({'name':'pytest','result':run(['python','-m','pytest','-q'],sandbox,300)})
   elif (sandbox/'test').exists(): report['tests'].append({'name':'unittest','result':run(['python','-m','unittest','discover','-v'],sandbox,300)})
   else: report['tests'].append({'name':'tests','result':'NO_TEST_SUITE_FOUND'})
   ok=all((x.get('result',{}).get('returncode',0)==0) if isinstance(x.get('result'),dict) else True for x in report['tests'])
   report['status']='PASSED_ISOLATED_TESTS' if ok else 'REJECTED_TEST_FAILURE'
   report['deployment']='eligible_for_review_only' if ok else 'blocked'
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':report['status']}))

if __name__=='__main__':main()
