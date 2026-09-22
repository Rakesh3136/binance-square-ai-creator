"""Run Jev against the final drafted post when configured.

Jev is a second opinion. Deterministic gates remain authoritative and Jev can
only approve a setup that has already passed them.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from jev_decision_gate import evaluate

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'data/live/authoritative_opportunity.json'
SIGNAL=ROOT/'data/live/signal_first_routing.json'
ENSEMBLE=ROOT/'data/live/decision_ensemble.json'
OUT=ROOT/'data/live/jev_decision.json'


def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}


def draft_text(path: str) -> str:
    try:
        x=load(Path(path))
        if isinstance(x.get('draft'),dict):
            d=x['draft']; return str(d.get('post') or d.get('text') or '')
        return str(x.get('post') or x.get('text') or '')
    except Exception: return ''


def main() -> int:
    frozen=load(FROZEN); signal=load(SIGNAL); ensemble=load(ENSEMBLE)
    path=os.getenv('DRAFT_PATH','').strip()
    post=draft_text(path)
    if not post:
        raise SystemExit('Jev runtime gate: final draft text is missing')
    evidence=[]
    for key in ('reason','instruction','signal_thesis_key'):
        if frozen.get(key): evidence.append(f"{key}: {frozen[key]}")
    ev=frozen.get('evidence')
    if isinstance(ev,dict):
        evidence.extend(f"{k}: {v}" for k,v in list(ev.items())[:8])
    evidence.append(f"ensemble_decision: {ensemble.get('decision','UNKNOWN')}")
    deterministic_ok=(frozen.get('binance_verified') is True
                       and str(frozen.get('direction') or '').upper() in {'LONG','SHORT'}
                       and all(frozen.get(k) is not None for k in ('entry_trigger','tp1','tp2','sl'))
                       and signal.get('publish') is True
                       and ensemble.get('decision') == 'PASS')
    result=evaluate(
        symbol=str(frozen.get('symbol') or ''),
        category=str(frozen.get('category') or ''),
        post=post,
        direction=str(frozen.get('direction') or ''),
        entry=frozen.get('entry_trigger'), tp1=frozen.get('tp1'), tp2=frozen.get('tp2'), sl=frozen.get('sl'),
        opportunity_score=float(frozen.get('effective_score') or frozen.get('score') or 0),
        quality_score=float(frozen.get('quality_score') or 0),
        evidence=evidence,
        deterministic_ok=deterministic_ok,
    )
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'enabled':result.get('enabled'),'status':result.get('status'),'action':result.get('action'),'publish':result.get('publish'),'confidence':result.get('confidence')},indent=2))
    # If configured, Jev must positively approve. If unavailable, the local
    # deterministic/ensemble gates remain the authority rather than failing the run.
    if result.get('enabled') and result.get('publish') is not True:
        return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
