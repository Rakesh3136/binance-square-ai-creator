"""Creator 7.3 — Causal Strategy Optimizer.

Uses observational, within-creator comparisons to estimate which controlled
content dimensions are associated with better outcomes. It does NOT claim
scientific causality from simple correlations. Recommendations are promoted
only when there is repeated evidence, adequate variation, and a measurable
outcome difference. Safety/editorial constraints remain hard constraints.
"""
from __future__ import annotations
import json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analytics/creator_7_3_causal_effects.json'
REPORT=ROOT/'data/intelligence/creator_7_3_report.json'
STRATEGY=ROOT/'analytics/creator_7_3_strategy.json'
MEMORY=ROOT/'analytics/strategy_memory.json'
SOURCE=ROOT/'analytics/creator_7_2_outcomes.jsonl'

DIMS=('experiment_format','category','style','hook_type','visual_type')


def rows():
    if not SOURCE.exists(): return []
    out=[]
    for line in SOURCE.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict) and isinstance(x.get('metrics'),dict): out.append(x)
        except Exception: pass
    return out

def num(x):
    try:
        y=float(x); return y if math.isfinite(y) else 0.0
    except: return 0.0

def outcome(x):
    if x.get('outcome_score') is not None:return num(x['outcome_score'])
    m=x['metrics']; v=num(m.get('views'))
    if not v:return 0
    return (num(m.get('likes'))+2*num(m.get('comments'))+3*num(m.get('shares')))/v*1000

def median(a):
    a=sorted(a); n=len(a)
    return 0 if not a else a[n//2] if n%2 else (a[n//2-1]+a[n//2])/2

def effect(rows_, dim, value):
    treated=[outcome(x) for x in rows_ if x.get(dim)==value]
    control=[outcome(x) for x in rows_ if x.get(dim)!=value]
    if len(treated)<3 or len(control)<3:return None
    tm,cm=median(treated),median(control)
    return {'dimension':dim,'value':value,'treated_sample':len(treated),'control_sample':len(control),'treated_median':round(tm,4),'control_median':round(cm,4),'lift_points':round(tm-cm,4),'lift_percent':round((tm-cm)/max(abs(cm),1)*100,2)}

def main():
    data=rows(); effects=[]
    for dim in DIMS:
        values=sorted({str(x.get(dim) or 'unknown') for x in data})
        for value in values:
            e=effect(data,dim,value)
            if e: effects.append(e)
    effects.sort(key=lambda x:(x['lift_points'],x['treated_sample']),reverse=True)
    # A recommendation needs >=5 observations in the treatment group and >=5 controls.
    recommendations=[]
    for e in effects:
        if e['treated_sample']>=5 and e['control_sample']>=5 and abs(e['lift_percent'])>=15:
            recommendations.append({**e,'decision':'PREFER' if e['lift_points']>0 else 'DEPRIORITIZE','confidence':'OBSERVATIONAL_REPEATED'})
    now=datetime.now(timezone.utc).isoformat()
    strategy={'version':'7.3','generated_at':now,'status':'ACTIVE' if len(data)>=10 else 'EXPLORATION','sample_size':len(data),'effects':effects[:100],'recommendations':recommendations[:30], 'causal_claim_policy':'No causal claim from observational data alone. Treat effects as hypotheses until controlled A/B or randomized timing/format tests confirm them.','exploration_rate':0.20 if len(data)>=30 else 0.35,'minimum_treatment_sample':5,'minimum_control_sample':5,'minimum_absolute_lift_percent':15,'hard_constraints':['factual_accuracy','originality','verified_market_data','no_fake_engagement','no_guaranteed_returns']}
    STRATEGY.write_text(json.dumps(strategy,indent=2,ensure_ascii=False),encoding='utf-8')
    OUT.write_text(json.dumps({'generated_at':now,'effects':effects},indent=2,ensure_ascii=False),encoding='utf-8')
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({'version':'7.3','generated_at':now,'sample_size':len(data),'top_effects':effects[:30],'recommendations':recommendations[:30]},indent=2,ensure_ascii=False),encoding='utf-8')
    memory={}
    try: memory=json.loads(MEMORY.read_text(encoding='utf-8')) if MEMORY.exists() else {}
    except: pass
    memory['creator_7_3']=strategy
    MEMORY.write_text(json.dumps(memory,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'7.3','sample_size':len(data),'effects_measured':len(effects),'recommendations':len(recommendations),'report':str(REPORT)},ensure_ascii=False))
if __name__=='__main__':main()
