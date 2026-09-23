"""Recover a blocked publication by selecting a different verified opportunity.

This recovery lane never bypasses evidence, Jev, editorial, visual, W2E or
publication gates. It only broadens candidate discovery when the primary
candidate is a recent duplicate.
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'data/live/publication_result.json'
ROUTING=ROOT/'data/live/signal_first_routing.json'


def run(name,*args,env=None):
    cmd=[sys.executable,str(ROOT/'src'/name),*args]
    print('RECOVERY_RUN', ' '.join(cmd))
    return subprocess.run(cmd,cwd=ROOT,env=env or os.environ.copy(),check=False).returncode


def load(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}


def main():
    result=load(RESULT)
    if result.get('status')!='PUBLISH_BLOCKED_DUPLICATE':
        print('No duplicate publication to recover; leaving authoritative state unchanged.')
        return 0

    base=os.environ.copy()
    # Keep flow-confidence and OHLCV requirements intact. Only lower discovery
    # score so another independently verified candidate can enter consideration.
    for minimum in ('65','60','55'):
        env=base.copy(); env['SIGNAL_FIRST_MIN_SCORE']=minimum
        env['SIGNAL_FIRST_TEXT_SIMILARITY']='0.72'
        rc=run('signal_first_router.py',env=env)
        if rc!=0: continue
        routing=load(ROUTING)
        if routing.get('publish') is True and routing.get('selected'):
            print('RECOVERY_SELECTED',json.dumps({
                'symbol':routing.get('selected',{}).get('symbol'),
                'lane':routing.get('selected',{}).get('lane'),
                'score':routing.get('selected',{}).get('score'),
                'minimum_score':minimum,
            }))
            return 0
        print('RECOVERY_NO_ELIGIBLE_CANDIDATE',minimum,routing.get('blocked_candidates'))

    print('No different verified candidate was found; preserving duplicate safety gate.')
    return 0

if __name__=='__main__': raise SystemExit(main())
