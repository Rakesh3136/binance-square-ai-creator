"""Creator 22.3 — audience-aware draft brief.

Bridges learned hook/format patterns into the actual content-generation input.
It does not generate or publish content itself; it creates bounded guidance for
the existing creator pipeline. Historical performance remains observational.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INTEL=ROOT/'data/live/creator_22_2_editorial_intelligence.json'
PREF=ROOT/'data/live/editorial_preflight.json'
OUT=ROOT/'data/live/creator_22_3_draft_brief.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    intel=load(INTEL); pre=load(PREF); guidance=intel.get('guidance') or []
    preferred=[]; reduce=[]
    for g in guidance:
        if g.get('preferred_for_testing'): preferred.extend(g['preferred_for_testing'][:2])
        if g.get('reduce_repetition'): reduce.extend(g['reduce_repetition'][-2:])
    selected=pre.get('selected_opportunity') or {}
    category=str(selected.get('category') or 'market_opportunity')
    brief={
      'version':'22.3','generated_at':datetime.now(timezone.utc).isoformat(),
      'status':'READY' if guidance else 'NO_LEARNED_PATTERN',
      'selected_opportunity':selected,
      'editorial_instruction':{
        'use_learned_patterns_as_testing_preferences':True,
        'preferred_patterns':preferred[:6],
        'patterns_to_reduce':reduce[:6],
        'category':category,
        'one_primary_hook':True,
        'one_primary_format':True,
        'visual_should_support_claim':True,
        'avoid_generic_price_recap':True,
        'do_not_copy_individual_creator':True,
        'do_not_claim_algorithm_knowledge':True,
        'do_not_infer_revenue':True,
        'observation_not_causality':True,
        'accuracy_over_virality':True,
      },
      'fallback_if_no_pattern':'Use the existing evidence-based editorial contract and explore a new hook/format rather than fabricating a winner.'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    pre['creator_22_3_draft_brief']=brief
    PREF.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':brief['status'],'preferred_patterns':len(preferred),'reduced_patterns':len(reduce)},indent=2))
if __name__=='__main__':main()
