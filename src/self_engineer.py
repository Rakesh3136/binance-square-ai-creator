"""Local-only bounded self-development controller for NIC.

External LLMs are optional. NIC remains operational without Gemini/OpenAI/API keys.
This controller analyses existing telemetry and produces bounded improvement plans;
it never changes credentials, safety gates, tests or workflow infrastructure itself.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/self_engineering_report.json'

def load(p,default=None):
    try:
        x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def main():
    memory=load(ROOT/'analytics/strategy_memory.json',{}) or {}
    feedback=load(ROOT/'data/live/feedback_strategy.json',{}) or {}
    funnel=load(ROOT/'data/live/monetization_funnel_optimizer.json',{}) or {}
    portfolio=load(ROOT/'data/live/creator_portfolio_intelligence.json',{}) or {}
    recommendations=[]
    if funnel.get('next_tests'): recommendations.append({'area':'monetization','action':'run_one_bounded_funnel_experiment','reason':'funnel optimizer supplied evidence-backed tests'})
    if portfolio: recommendations.append({'area':'content_portfolio','action':'rebalance_exploration_vs_repetition','reason':'portfolio intelligence is available'})
    if feedback.get('repeated_observations',0): recommendations.append({'area':'learning','action':'feed_repeated_observations_into_next_cycle','reason':'repeated observations exist'})
    recommendations.append({'area':'reliability','action':'keep_external_model_provider_optional','reason':'NIC must remain operational without API keys'})
    report={'version':'local-only-1.0','status':'LOCAL_ONLY_READY','generated_at':datetime.now(timezone.utc).isoformat(),'external_model_required':False,'policy':'NIC remains autonomous using deterministic/local intelligence; external models are optional accelerators only.','recommendations':recommendations,'telemetry_summary':{'memory_available':bool(memory),'feedback_available':bool(feedback),'funnel_available':bool(funnel),'portfolio_available':bool(portfolio)}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'external_model_required':False,'recommendations':len(recommendations)},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
