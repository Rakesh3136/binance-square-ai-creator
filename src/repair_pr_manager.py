"""Prepare a controlled self-repair change for review.

This module does not push to main or merge a PR. It records the sandbox result
and creates a review-ready change plan. A separate CI/reviewer can decide whether
to apply and merge the candidate.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'data/intelligence/repair_sandbox_report.json'
PLAN=ROOT/'data/intelligence/self_repair_pr_plan.json'

def main():
 try:r=json.loads(REPORT.read_text(encoding='utf-8'))
 except Exception:r={}
 ok=r.get('status')=='PASSED_ISOLATED_TESTS'
 now=datetime.now(timezone.utc).isoformat()
 plan={'generated_at':now,'status':'READY_FOR_REVIEW' if ok else 'BLOCKED','head_branch':'ai/self-repair-automation','base_branch':'main','sandbox_status':r.get('status'),'merge_allowed':False,'required_checks':['isolated patch validation','CI tests','security/secrets scan','manual or explicit deployment approval'],'rollback':'Revert the PR commit if post-merge checks regress.','reason':'Sandbox-tested candidate may be reviewed; no automatic merge is permitted.' if ok else 'Candidate did not pass isolated sandbox tests.'}
 PLAN.parent.mkdir(parents=True,exist_ok=True); PLAN.write_text(json.dumps(plan,indent=2),encoding='utf-8'); print(json.dumps(plan))
if __name__=='__main__':main()
