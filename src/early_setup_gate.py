"""Hard publication gate for early-mover hypotheses.

Normal editorial stories may pass through unchanged. A next-mover/full-universe
story must contain independent participation evidence plus a real trigger and
invalidation. Otherwise the cycle waits instead of manufacturing a prediction.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'data/live/authoritative_opportunity.json';FLOW=ROOT/'data/live/full_universe_flow.json';OUT=ROOT/'data/live/early_setup_gate.json'
EARLY_CATS={'next_gainer_candidate','next_loser_candidate','capital_flow_long','capital_flow_short'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def num(v):
    try:return float(v)
    except Exception:return 0.0
def main():
    frozen=load(FROZEN);flow=load(FLOW);cat=str(frozen.get('category') or frozen.get('lane') or '').lower();symbol=str(frozen.get('symbol') or '').upper();
    rows={str(x.get('symbol') or '').upper():x for x in (flow.get('top_flow_candidates') or []) if isinstance(x,dict)}
    row=rows.get(symbol,{})
    early_lane=cat in EARLY_CATS or bool(row.get('early_mover')) or str(row.get('flow_state') or '').upper() in {'EARLY','DEVELOPING'}
    reasons=[];state=str(row.get('flow_state') or '').upper();score=num(row.get('discovery_score'));vol=num(row.get('volume_acceleration'));med=num(row.get('volume_vs_24h_median'));oi=num(row.get('oi_change_3h_pct'));move=abs(num(row.get('price_change_percent')));dist=num(row.get('breakout_distance_pct'))
    evidence=sum(bool(row.get(k) not in (None,'')) for k in ('volume_acceleration','volume_vs_24h_median','relative_strength_24h','oi_change_3h_pct','breakout_distance_pct'))
    participation=(vol>=1.5 and med>=1.2) or oi>=2
    if not early_lane:
        status='PASS_NORMAL_LANE';allowed=True
    else:
        if state in {'LATE','EXHAUSTED'}:reasons.append(f'flow_state={state}')
        if state not in {'EARLY','DEVELOPING','CONFIRMED'}:reasons.append('no_qualified_early_state')
        if score<45:reasons.append('discovery_score_below_45')
        if not participation:reasons.append('insufficient_independent_participation_evidence')
        if evidence<3:reasons.append('fewer_than_3_observed_flow_structure_fields')
        if move>8:reasons.append('move_too_extended_for_early_lane')
        allowed=not reasons;status='PASS_EARLY_SETUP' if allowed else 'WAIT_FOR_CONFIRMATION'
    payload={'version':'1.0','status':status,'allowed':allowed,'symbol':symbol,'category':cat,'flow_state':state,'discovery_score':score,'evidence_fields':evidence,'participation_evidence':participation,'reasons':reasons,'policy':['No generic fallback is allowed when an early setup fails.','A confirmed setup still needs a concrete trigger and invalidation in the authoring contract.','This gate does not guarantee a future move.']}
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(payload,indent=2))
    if not allowed:raise SystemExit('WAIT_FOR_CONFIRMATION: early-mover evidence gate failed')
if __name__=='__main__':main()
