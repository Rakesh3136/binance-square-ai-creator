"""Independent decision ensemble for the frozen opportunity.

The ensemble invokes optional local Qwen/Gemma critics when an Ollama runtime is
available, then combines them with deterministic and specialist evidence. It
never becomes a market-data authority.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data/live'; OUT=LIVE/'decision_ensemble.json'

def load(name):
    try:
        x=json.loads((LIVE/name).read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}

def run_optional_local_critics():
    script=ROOT/'src/local_model_critic.py'
    if not script.exists(): return
    try:
        subprocess.run([sys.executable,str(script)],cwd=str(ROOT),check=False,timeout=110)
    except Exception as exc:
        (LIVE/'local_model_critic_error.json').write_text(json.dumps({'error':str(exc)[:500],'at':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')

def main():
    run_optional_local_critics()
    frozen=load('authoritative_opportunity.json'); signal=load('signal_first_routing.json')
    specialists=[('adversarial','adversarial_decision.json'),('counterfactual','counterfactual_analysis.json'),('research','research_intelligence.json'),('local_models','local_model_critic.json')]
    direction=str(frozen.get('direction') or '').upper()
    contract=all(frozen.get(k) is not None for k in ('entry_trigger','tp1','tp2','sl'))
    signal_ok=signal.get('publish') is True and bool(signal.get('selected'))
    frozen_ok=bool(frozen.get('binance_verified')) and direction in {'LONG','SHORT'} and contract
    votes=[{'agent':'signal_first','decision':'PASS' if signal_ok else 'BLOCK','reason':'authoritative signal router'},
           {'agent':'frozen_contract','decision':'PASS' if frozen_ok else 'BLOCK','reason':'live symbol + direction + complete setup contract'}]
    for name,path in specialists:
        data=load(path)
        if not data: continue
        decision=str(data.get('decision') or data.get('status') or '').upper()
        if decision in {'UNAVAILABLE','SKIPPED'}: continue
        blocked=data.get('blocked') is True or decision in {'BLOCK','BLOCKED','FAIL','FAILED'}
        approved=data.get('approved') is True or data.get('publish') is True or data.get('publish_authorized') is True or decision in {'PASS','PASSING','APPROVE','APPROVED'}
        votes.append({'agent':name,'decision':'BLOCK' if blocked else ('PASS' if approved else 'REVIEW'),'reason':str(data.get('reason') or data.get('message') or 'specialist output')[:500]})
    passes=sum(v['decision']=='PASS' for v in votes); blocks=sum(v['decision']=='BLOCK' for v in votes); reviews=sum(v['decision']=='REVIEW' for v in votes)
    decision='BLOCK' if not frozen_ok or not signal_ok else ('REVIEW' if blocks or reviews else 'PASS')
    result={'version':'1.3','generated_at':datetime.now(timezone.utc).isoformat(),'symbol':frozen.get('symbol'),'direction':direction,'decision':decision,'publish_authorized':decision=='PASS','vote_count':len(votes),'passes':passes,'blocks':blocks,'reviews':reviews,'disagreement':bool(blocks or reviews),'votes':votes,'policy':'Independent reviewers may require review, but cannot override deterministic market/evidence failures.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    try:
        subprocess.run([sys.executable,str(ROOT/'src/decision_calibration.py')],cwd=str(ROOT),check=False,timeout=30)
    except Exception: pass
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if decision=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
