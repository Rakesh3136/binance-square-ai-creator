"""Creator 22.2 — hook + format intelligence.

Converts repeated explicit audience outcomes into bounded editorial guidance.
It learns which hook/format/visual combinations deserve more testing and which
should be reduced. Observation is never treated as proof of causality.
"""
from __future__ import annotations
import json, statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTCOMES=ROOT/'data/live/creator_7_2_outcomes.jsonl'
BOARD=ROOT/'data/live/creator_22_0_audience_board.json'
OUT=ROOT/'data/live/creator_22_2_editorial_intelligence.json'
REPORT=ROOT/'data/intelligence/creator_22_2_report.json'

def rows(p):
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding='utf-8').splitlines()[-1000:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def num(x):
    try:return float(x)
    except Exception:return None

def main():
    outcomes=rows(OUTCOMES)
    board={}
    try: board=json.loads(BOARD.read_text(encoding='utf-8'))
    except Exception: pass
    samples=[]
    for r in outcomes:
        metrics={k:num(r.get(k)) for k in ('views','likes','replies','shares','followers_gained')}
        if not any(v is not None for v in metrics.values()): continue
        samples.append({**r,**metrics})
    dimensions=('hook_type','format','visual_type','category')
    guidance=[]
    for dim in dimensions:
        groups={}
        for r in samples:
            value=str(r.get(dim) or 'unknown').strip().lower()
            groups.setdefault(value,[]).append(r)
        scored=[]
        for value,group in groups.items():
            if value=='unknown' or len(group)<3: continue
            views=[r['views'] for r in group if r['views'] is not None]
            replies=[r['replies'] for r in group if r['replies'] is not None]
            followers=[r['followers_gained'] for r in group if r['followers_gained'] is not None]
            scored.append({'dimension':dim,'value':value,'samples':len(group),'avg_views':round(statistics.mean(views),2) if views else None,'avg_replies':round(statistics.mean(replies),2) if replies else None,'avg_followers_gained':round(statistics.mean(followers),2) if followers else None})
        scored.sort(key=lambda x:(x['avg_views'] or 0,x['avg_replies'] or 0,x['avg_followers_gained'] or 0),reverse=True)
        if scored:
            guidance.append({'dimension':dim,'preferred_for_testing':scored[:3],'reduce_repetition':list(reversed(scored[-3:])),'confidence':'OBSERVATIONAL','minimum_samples':3})
    # Explicitly expose the audience board but never turn it into an automatic causal claim.
    result={'version':'22.2','generated_at':datetime.now(timezone.utc).isoformat(),'source_samples':len(samples),'audience_board_available':bool(board),'guidance':guidance,'rules':{'explicit_metrics_only':True,'observation_not_causality':True,'minimum_samples':3,'bounded_guidance_only':True,'no_engagement_manipulation':True,'accuracy_over_growth':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    REPORT.write_text(json.dumps({'version':'22.2','status':'OK','samples':len(samples),'dimensions_analyzed':len(guidance),'output':str(OUT.relative_to(ROOT))},indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
