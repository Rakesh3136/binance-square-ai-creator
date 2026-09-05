"""Creator 7.5 — Growth Portfolio Controller.

Builds a diversified content portfolio from verified outcomes. It prevents
single-asset overfitting and gives the autonomous creator a measurable mix of
reach, discussion, education and market-intelligence content.
"""
from __future__ import annotations
import json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'analytics/creator_7_2_outcomes.jsonl'
MEMORY=ROOT/'analytics/strategy_memory.json'
OUT=ROOT/'analytics/creator_7_5_growth_portfolio.json'
REPORT=ROOT/'data/intelligence/creator_7_5_report.json'

BUCKETS=('BREAKING_MARKET','EXPLAINER','DATA_DEEP_DIVE','DEBATE','MACRO_REGULATION')


def load(path, default):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default

def rows():
    if not SOURCE.exists():return []
    out=[]
    for line in SOURCE.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict) and isinstance(x.get('metrics'),dict):out.append(x)
        except Exception:pass
    return out

def num(x):
    try:
        y=float(x);return y if math.isfinite(y) else 0.0
    except Exception:return 0.0

def score(x):
    if x.get('outcome_score') is not None:return num(x['outcome_score'])
    m=x.get('metrics',{});v=num(m.get('views'))
    return 0 if v<=0 else (num(m.get('likes'))+2*num(m.get('comments'))+3*num(m.get('shares'))+2*num(m.get('quotes')))/v*1000

def bucket(x):
    c=str(x.get('category') or '').lower()
    if any(k in c for k in ('breaking','news','alert')):return 'BREAKING_MARKET'
    if any(k in c for k in ('macro','regulation','policy','institutional')):return 'MACRO_REGULATION'
    if any(k in c for k in ('analysis','technical','onchain','data')):return 'DATA_DEEP_DIVE'
    if any(k in c for k in ('opinion','debate','community')):return 'DEBATE'
    return 'EXPLAINER'

def main():
    data=rows();counts=Counter(bucket(x) for x in data);means={}
    for b in BUCKETS:
        vals=[score(x) for x in data if bucket(x)==b]
        means[b]=round(sum(vals)/len(vals),4) if vals else 0
    total=max(len(data),1)
    # Target mix: enough reach opportunities, but never let one bucket dominate.
    target={'BREAKING_MARKET':0.25,'EXPLAINER':0.25,'DATA_DEEP_DIVE':0.20,'DEBATE':0.15,'MACRO_REGULATION':0.15}
    if len(data)<10:
        target={'BREAKING_MARKET':0.20,'EXPLAINER':0.30,'DATA_DEEP_DIVE':0.20,'DEBATE':0.15,'MACRO_REGULATION':0.15}
    gaps={b:round(target[b]-counts[b]/total,4) for b in BUCKETS}
    priority=sorted(BUCKETS,key=lambda b:(gaps[b],means[b]),reverse=True)
    portfolio={
      'version':'7.5','generated_at':datetime.now(timezone.utc).isoformat(),'sample_size':len(data),
      'content_mix_target':target,'observed_bucket_counts':dict(counts),'observed_bucket_mean_scores':means,
      'next_bucket_priority':priority[:3],
      'rules':[
        'Diversify across market, education, data, debate and macro/regulation opportunities.',
        'Do not force a bucket when no verified high-quality story exists.',
        'A genuinely major verified breaking event may override the normal mix.',
        'Do not overfit to a single asset or repeated topic.',
        'Optimize for followers and substantive engagement, not fake engagement.',
        'Revenue is used only when explicitly verified; views never imply revenue.'
      ],
      'next_action':f"Prefer a {priority[0]} opportunity when it passes the existing editorial and market-data gates; otherwise choose the strongest verified opportunity regardless of bucket."
    }
    OUT.write_text(json.dumps(portfolio,indent=2,ensure_ascii=False),encoding='utf-8')
    memory=load(MEMORY,{})
    memory['creator_7_5']=portfolio
    overlay=memory.get('learning_overlay') if isinstance(memory.get('learning_overlay'),dict) else {}
    overlay['growth_portfolio']={'instruction':portfolio['next_action'],'priority_buckets':priority[:3],'target_mix':target}
    memory['learning_overlay']=overlay
    MEMORY.write_text(json.dumps(memory,indent=2,ensure_ascii=False),encoding='utf-8')
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({'version':'7.5','generated_at':portfolio['generated_at'],'sample_size':len(data),'portfolio':portfolio},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'7.5','sample_size':len(data),'next_bucket':priority[0],'report':str(REPORT)},ensure_ascii=False))

if __name__=='__main__':main()
