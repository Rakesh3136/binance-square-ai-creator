"""Living Brain: continuous strategic self-review for the autonomous creator.

This is a decision layer, not a claim of consciousness. It asks what is missing,
what changed, what is underperforming, and what should be tested next. It can
propose engineering changes, but executable self-modification remains gated by
review/tests rather than being silently deployed by the model.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/intelligence/living_brain.json'
STATE=ROOT/'data/intelligence/living_brain_state.json'
PLAN=ROOT/'data/intelligence/self_improvement_plan.json'

def read(rel):
 p=ROOT/rel
 try:
  x=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
  return x if isinstance(x,dict) else {}
 except Exception:return {}

def num(v):
 try:return float(v)
 except:return 0.0

def main():
 files={k:read(v) for k,v in {
  'market':'data/live/market_snapshot.json','news':'data/live/news_snapshot.json','brain':'data/live/creator_brain_decision.json',
  'preflight':'data/live/editorial_preflight.json','performance':'data/intelligence/performance_feedback.json',
  'calls':'data/intelligence/call_tracker.json','dashboard':'data/intelligence/growth_dashboard.json',
  'strategy':'analytics/strategy_memory.json','patterns':'data/intelligence/creator_patterns.json',
  'audience':'data/intelligence/audience_profile.json','context':'data/live/publication_context.json'}.items()}
 now=datetime.now(timezone.utc); dash=files['dashboard']; today=dash.get('today',{}); week=dash.get('last_7_days',{})
 missing=[]; actions=[]
 if today.get('followers') is None: missing.append('verified total follower count'); actions.append(('HIGH','Connect a supported account-level follower metric for day-over-day growth.'))
 if num(week.get('views'))==0: actions.append(('CRITICAL','Repair/verify Square performance collection; do not pretend the learning loop can see engagement without metrics.'))
 if not files['news'].get('articles'): missing.append('fresh news feed'); actions.append(('HIGH','Repair or expand news discovery before publishing news-led content.'))
 if not files['market']: missing.append('fresh market snapshot'); actions.append(('CRITICAL','Stop unsupported market claims until fresh market data exists.'))
 if not files['context'].get('visual_decision'): actions.append(('HIGH','Keep TradingView visual requirements explicit for technical posts.'))
 audience=files['audience'].get('signals') or {}; rr=num(audience.get('replies_per_view')); lr=num(audience.get('likes_per_view')); fr=num(audience.get('followers_per_view'))
 if rr<0.005: actions.append(('HIGH','Test specific A/B, level-choice and breakout/fakeout questions; rotate hooks.'))
 if lr<0.01: actions.append(('MEDIUM','Test stronger first-line hooks and clearer chart/news payoff; never beg for likes.'))
 if fr<0.002: actions.append(('HIGH','Test recurring series, verified call follow-ups and stronger value proposition for followers.'))
 coverage=files['preflight'].get('engagement_strategy',{}).get('content_coverage') or []
 if len(coverage)<8: actions.append(('MEDIUM','Expand research universe beyond price-only stories.'))
 questions=['What produced measurable value?','What failed and why?','What changed in crypto today?','What are we missing?','Which format should we test next?','What evidence would change our decision?','Which previous call needs a verified update?','Where is the audience dropping off?']
 experiments=[
  {'name':'hook_rotation','goal':'raise reply/view conversion','metric':'replies_per_view'},
  {'name':'news_plus_chart','goal':'connect catalyst to price action','metric':'engagement_rate'},
  {'name':'call_outcome_series','goal':'build trust and returning followers','metric':'followers_per_view'},
  {'name':'format_rotation','goal':'prevent creative fatigue','metric':'format_level_engagement'},
  {'name':'topic_gap_scan','goal':'find important crypto stories competitors are covering that we missed','metric':'missed_opportunity_count'},
 ]
 priorities=sorted(actions,key=lambda x:{'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}.get(x[0],4))[:15]
 plan={'generated_at':now.isoformat(),'mission':'Continuously improve useful output, verified accuracy, engagement, follower conversion and eligible monetization.','gaps':missing,'priorities':priorities,'self_questions':questions,'experiments':experiments,'code_improvement_policy':{'propose_changes':True,'write_deployable_code_automatically':False,'require_tests':True,'require_review_or_explicit_pipeline_gate':True,'require_rollback':True},'financial_urgency':{'level':'HIGH','meaning':'Prioritize sustainable revenue potential and learning speed.','forbidden':'No guaranteed profits, fabricated results, fake engagement, spam, or reckless calls.'}}
 plan['plan_id']='sip-'+now.strftime('%Y%m%d')+'-'+hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()[:12]
 decision={'generated_at':now.isoformat(),'brain_version':2,'mode':'continuous_self_improvement','mission':plan['mission'],'operating_principle':'Protect runway, maximize useful output, learn quickly, and never sacrifice truth for a short-term metric.','financial_urgency':plan['financial_urgency'],'system_health':{'missing_inputs':missing,'priority_actions':priorities},'today':today,'seven_day':week,'audience_signals':audience,'research_audit':{'fresh_news_items':len(files['news'].get('articles') or []),'market_snapshot_available':bool(files['market']),'coverage_topics':coverage},'self_questions':questions,'next_experiments':experiments,'next_action':'Feed priorities into Creator Brain before the next production cycle.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False),encoding='utf-8'); PLAN.write_text(json.dumps(plan,indent=2,ensure_ascii=False),encoding='utf-8'); STATE.write_text(json.dumps({'last_run':now.isoformat(),'plan_id':plan['plan_id'],'cycle_count':int(read('data/intelligence/living_brain_state.json').get('cycle_count',0))+1},indent=2),encoding='utf-8')
 print(json.dumps({'status':'OK','plan_id':plan['plan_id'],'priority_actions':len(priorities),'missing_inputs':missing},ensure_ascii=False))
if __name__=='__main__':main()
