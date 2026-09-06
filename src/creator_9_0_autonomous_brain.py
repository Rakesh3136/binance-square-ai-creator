"""Creator 9.0 — Autonomous Creator Brain.

Consolidates learned strategy into one explicit decision policy. It does not
publish or fabricate metrics; it produces a machine-readable directive for the
existing publishing pipeline.
"""
from __future__ import annotations
import json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MEMORY=ROOT/'analytics/strategy_memory.json'
PERF=ROOT/'data/intelligence/performance_feedback.json'
BRAIN=ROOT/'data/live/creator_brain_decision.json'
MISSION=ROOT/'data/live/creator_mission_7.json'
AUTHORITATIVE=ROOT/'data/live/authoritative_opportunity.json'
OUT=ROOT/'data/live/creator_9_0_brain_state.json'
REPORT=ROOT/'data/intelligence/creator_9_0_report.json'

def load(p, default):
    try:
        x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
        return x if isinstance(x,dict) else default
    except Exception:return default

def num(x):
    try:
        y=float(x); return y if math.isfinite(y) else 0.0
    except Exception:return 0.0

def main():
    memory=load(MEMORY,{})
    perf=load(PERF,{})
    brain=load(BRAIN,{})
    mission=load(MISSION,{})
    auth=load(AUTHORITATIVE,{})
    now=datetime.now(timezone.utc).isoformat()
    sample=int(num(perf.get('observation_count')))
    promotion=bool(perf.get('promotion_allowed',False))
    winners=perf.get('learned_preferences') or {}
    symbol=str(auth.get('symbol') or brain.get('symbol') or '').upper().replace('USDT','')
    recent=memory.get('recent_performance_observations') or []
    recent_assets=[str(x.get('topic') or x.get('symbol') or '').upper().replace('USDT','') for x in recent]
    repeats=Counter(x for x in recent_assets if x)
    repeated_asset=max(repeats.items(),key=lambda z:z[1]) if repeats else ('',0)

    # Decision hierarchy: hard editorial constraints > fresh verified opportunity
    # > repeated evidence > exploration. No single weak metric can override it.
    learned=[]
    for dimension,info in winners.items():
        if isinstance(info,dict) and info.get('prefer') and promotion:
            learned.append({'dimension':dimension,'value':info['prefer'],'reason':info.get('reason','repeated evidence')})

    if not symbol:
        action='WAIT_FOR_VALID_OPPORTUNITY'
        confidence='LOW'
    elif repeated_asset[1]>=2 and repeated_asset[0]==symbol and not auth.get('news_authoritative'):
        action='PIVOT_IF_ALTERNATIVE_IS_STRONGER'
        confidence='MEDIUM'
    elif mission.get('decision')=='PUBLISH' and auth.get('binance_verified') is not False:
        action='PUBLISH_STRONG_OPPORTUNITY'
        confidence='MEDIUM' if sample<10 else 'HIGH'
    else:
        action='RESEARCH_OR_WAIT'
        confidence='LOW'

    exploration=0.35 if sample<30 else 0.20
    state={
      'version':'9.0','generated_at':now,'action':action,'confidence':confidence,
      'primary_asset':symbol,'observation_sample':sample,
      'promotion_allowed':promotion,'exploration_rate':exploration,
      'mission_goal':mission.get('primary_goal','maximize legitimate creator opportunity'),
      'strategy_layers':['7.2 outcomes','7.3 causal hypotheses','7.4 adaptive experiments','7.5 growth portfolio','8.0 revenue intelligence'],
      'learned_preferences':learned,
      'recent_asset_pressure':{'asset':repeated_asset[0],'recent_count':repeated_asset[1],'avoid_repetition':repeated_asset[1]>=2},
      'decision_order':['hard_constraints','verified_freshness','editorial_value','story_quality','repeated_performance','controlled_experiment','exploration'],
      'publisher_directive':{
        'choose_market_wide_opportunity':True,
        'prefer_fresh_verified_news_when_material':True,
        'use_real_market_data':True,
        'use_real_tradingview_visual_when_informative':True,
        'one_primary_experiment_variable':True,
        'optimize_for_substantive_engagement_and_follower_growth':True,
        'monetization_goal_is_verified_conversion_only':True,
        'revenue_must_be_explicitly_verified':True,
        'never_force_story_for_experiment':True,
        'never_infer_revenue_from_views':True,
        'never_claim_causality_from_observational_data':True,
        'never_publish_filler':True,
        'never_use_fake_engagement':True,
        'never_guarantee_returns':True,
      },
      'next_cycle':{
        'action':action,
        'instruction':('Publish only if the existing editorial/quality gates pass; use the brain as a strategy layer, not as permission to bypass them.' if action.startswith('PUBLISH') else 'Continue research, diversification or a quality opportunity search; skipping is valid when evidence is weak.'),
        'success_metrics':['views','likes','comments','shares','quotes','follower_growth','verified_conversion','verified_revenue'],
        'metric_priority':'verified_conversion_and_verified_revenue_when_available; otherwise substantive_engagement_and_follower_growth',
      },
      'guardrails':['factual_accuracy','originality','verified_market_data','no_fake_engagement','no_guaranteed_returns','no_revenue_inference','no_causal_overclaim'],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    REPORT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    memory['creator_9_0']=state
    overlay=memory.get('learning_overlay') if isinstance(memory.get('learning_overlay'),dict) else {}
    overlay['autonomous_brain']={
      'action':action,'confidence':confidence,'primary_asset':symbol,
      'instruction':state['next_cycle']['instruction'],'updated_at':now,
      'hard_constraints':state['guardrails']
    }
    memory['learning_overlay']=overlay
    MEMORY.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'OK','version':'9.0','action':action,'confidence':confidence,'primary_asset':symbol,'observation_sample':sample,'promotion_allowed':promotion},indent=2))

if __name__=='__main__':main()
