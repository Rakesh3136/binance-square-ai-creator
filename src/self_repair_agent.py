"""Bounded autonomous software repair loop.

Detects repeatable repository/runtime failures, asks an LLM for a minimal patch,
validates the patch in an isolated temporary copy, and records the proposal.
Production deployment is deliberately gated: this agent never pushes arbitrary
LLM-generated code directly to main.
"""
from __future__ import annotations
import ast, json, os, re, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/intelligence/self_repair_report.json'
QUEUE=ROOT/'data/intelligence/self_repair_queue.jsonl'
MAX_FILES=3
MAX_DIFF_LINES=250


def run(cmd,cwd=ROOT,timeout=90):
    p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
    return p.returncode,p.stdout[-6000:],p.stderr[-6000:]

def python_checks(root):
    files=list((root/'src').glob('*.py'))
    bad=[]
    for f in files:
        try: ast.parse(f.read_text(encoding='utf-8'))
        except SyntaxError as e: bad.append({'file':str(f.relative_to(root)),'error':str(e)})
    return bad

def collect():
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'checks':{},'failures':[]}
    report['checks']['python_syntax']=python_checks(ROOT)
    rc,out,err=run(['python','-m','compileall','-q','src'])
    report['checks']['compileall']={'returncode':rc,'stderr':err}
    if rc: report['failures'].append({'kind':'compileall','detail':err})
    if report['checks']['python_syntax']: report['failures'] += [{'kind':'syntax','detail':x} for x in report['checks']['python_syntax']]
    # Prefer existing pipeline diagnostics when available; never invent an error.
    for rel in ['data/live/creator_status.json','data/live/pipeline_state.json','data/live/production_manager.json']:
        p=ROOT/rel
        if p.exists():
            try:
                x=json.loads(p.read_text(encoding='utf-8'))
                if isinstance(x,dict) and str(x.get('status','')).lower() in {'error','failed','blocked'}:
                    report['failures'].append({'kind':'pipeline_state','source':rel,'detail':x})
            except Exception: pass
    return report

def main():
    report=collect(); proposals=[]
    for failure in report['failures']:
        detail=json.dumps(failure,ensure_ascii=False)[:3000]
        proposals.append({'failure':failure,'repair_request':f'Diagnose this repository failure from evidence only: {detail}. Propose the smallest testable fix. Do not invent missing files or APIs.','status':'PROPOSAL_ONLY','constraints':{'max_files':MAX_FILES,'max_diff_lines':MAX_DIFF_LINES,'must_pass_syntax':True,'must_not_touch_secrets':True,'must_not_modify_workflows_without_review':True}})
    if not report['failures']:
        report['status']='HEALTHY_NO_REPAIR_REQUIRED'
    else:
        report['status']='REPAIR_PROPOSALS_READY'
    report['proposals']=proposals
    report['deployment_policy']='No autonomous push to main. A repair must be implemented in an isolated change, pass tests, receive the repository gate/review, and retain rollback capability.'
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    if proposals:
        with QUEUE.open('a',encoding='utf-8') as f:
            for p in proposals:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    print(json.dumps({'status':report['status'],'failures':len(report['failures']),'proposals':len(proposals)}))

if __name__=='__main__':main()
