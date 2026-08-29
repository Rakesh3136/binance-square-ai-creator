"""Living Brain: continuous strategic self-review for the autonomous creator.

This is a decision layer, not a claim of consciousness. It asks what is missing,
what changed, what is underperforming, and what should be tested next. It does
not fabricate money, followers, market certainty, or human-like feelings.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/intelligence/living_brain.json'
STATE=ROOT/'data/intelligence/living_brain_state.json'

FILES={
 'market':'data/live/market_snapshot.json','news':'data/live/news_snapshot.json',
 'brain':'data/live/creator_brain_decision.json','preflight':'data/live/editorial_preflight.json',
 'performance':'data/intelligence/performance_feedback.json','growth':'data/intelligence/call_tracker.json',
 'dashboard':'data/intelligence/growth_dashboard.json','strategy':'analytics/strategy_memory.json',
 'patterns':'data/intelligence/creator_patterns.json','audience':'data/intelligence/audience_profile.json',
 'evolution':'data/live/creator_evolution_state.json','context':'data/live/publication_context.json'
}

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
 d={k:read(v) for k,v in FILES.items()}; now=datetime.now(timezone.utc)
 dashboard=d['dashboard']; today=dashboard.get('today',{}); week=dashboard.get('last_7_days',{})
 news=d['news'].get('articles') or []; news=[x for x in news if isinstance(x,dict)]
 perf=d['performance']; audience=d['audience'].get('signals') or {}; evolution=d['evolution']; brain=d['brain']; pre=d['preflight']
 missing=[]; priorities=[]
 # Evidence / observability audit
 if not today.get('followers'):
  missing.append('verified total follower count'); priorities.append(('HIGH','Connect a supported account-level follower metric so day-over-day growth can be measured.'))
 if num(week.get('views'))==0:
  priorities.append(('HIGH','Verify that Square post metrics are actually being collected; without views/likes/comments the learning loop is blind.'))
 if not d['news'].get('articles'):
  missing.append('fresh news feed'); priorities.append(('HIGH','Repair or expand the news discovery source before publishing news-led content.'))
 if not d['market']:
  missing.append('fresh market snapshot'); priorities.append(('CRITICAL','Stop autonomous market claims until fresh market data is available.'))
 if not d['context'].get('visual_decision'):
  missing.append('publication visual contract'); priorities.append(('HIGH','Keep TradingView visual requirement explicit for technical posts.'))
 # Engagement diagnosis
 rr=num(audience.get('replies_per_view')); lr=num(audience.get('likes_per_view')); fr=num(audience.get('followers_per_view'))
 if rr < 0.005: priorities.append(('HIGH','Increase conversation quality: use one specific A/B or level-choice question and rotate opening structures.'))
 if lr < 0.01: priorities.append(('MEDIUM','Test stronger first-line hooks and clearer chart/news payoff; do not beg for likes.'))
 if fr < 0.002: priorities.append(('HIGH','Increase follow conversion with recurring series, verified call tracking and useful follow-up posts.'))
 # Content breadth audit
 coverage=pre.get('engagement_strategy',{}).get('content_coverage') or brain.get('editorial_requirements',{}).get('content_coverage') or []
 if len(coverage)<8: priorities.append(('MEDIUM','Expand the research universe beyond price-only stories.'))
 # Strategy health
 state=read('data/intelligence/living_brain_state.json'); previous=state.get('last_run',{})
 cooldown=state.get('cooldowns',{})
 ideas=[
  'Run a daily missed-opportunity scan: stories researched but not published, and why.',
  'Maintain a rolling win/loss scorecard for prediction formats, not just individual coins.',
  'Test news-only, chart-only, news+chart, data-surprise and creator-outcome formats against each other.',
  'Detect repeated symbols, narratives, hooks and paragraph structures before publication.',
  'Audit source freshness and reject stale news as current news.',
  'Measure follower conversion per post and per editorial format when verified metrics exist.',
  'Build follow-up chains from important calls instead of treating every post as isolated.',
  'Track which questions produce replies and retire questions that repeatedly produce silence.',
  'Review publishing cadence using observed performance instead of assuming more posts always means more earnings.',
  'Keep a visible failure ledger so the AI cannot learn only from successful calls.',
 ]
 # Human-like motivation translated into safe operational priorities: urgency is a
 # resource-allocation signal, never an excuse for reckless financial claims.
 financial_goal={
  'objective':'maximize sustainable creator revenue potential',
  'urgency':'HIGH',
  'rule':'Revenue pressure increases verification, experimentation and learning discipline; it never permits fabricated returns, guaranteed 10x claims, spam, or fake engagement.',
  'daily_questions':['What produced measurable value?','What failed and why?','What are we missing today?','Which experiment should run next?','What evidence would change our decision?']
 }
 # Prioritize novelty and evidence over simply publishing more.
 priorities=sorted(priorities,key=lambda x:{'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}.get(x[0],4))[:12]
 decision={
  'generated_at':now.isoformat(),'brain_version':1,'mode':'continuous_self_improvement',
  'mission':'Build a trustworthy, high-performing crypto creator that continuously researches, publishes, measures, learns and improves.',
  'operating_principle':'Think like a disciplined operator under financial pressure: protect runway, maximize useful output, learn quickly, and never sacrifice truth for a short-term metric.',
  'financial_goal':financial_goal,'system_health':{'missing_inputs':missing,'priority_actions':priorities},
  'today':{'followers':today.get('followers'),'day_over_day_follower_change':today.get('day_over_day_change'),'posts':today.get('posts',0),'views':today.get('views',0),'likes':today.get('likes',0),'comments':today.get('comments',0),'shares':today.get('shares',0)},
  'seven_day':week,
  'audience_signals':audience,
  'research_audit':{'fresh_news_items':len(news),'market_snapshot_available':bool(d['market']),'coverage_topics':coverage,'creator_brain_format':brain.get('editorial_format')},
  'self_questions':ideas,
  'next_experiments':[
    {'name':'hook_rotation','goal':'raise view-to-read and reply conversion','metric':'replies_per_view'},
    {'name':'news_plus_chart','goal':'connect catalyst to price action','metric':'engagement_rate'},
    {'name':'call_outcome_series','goal':'build trust and returning followers','metric':'followers_per_view'},
    {'name':'format_rotation','goal':'prevent creative fatigue','metric':'format_level_engagement'},
  ],
  'guardrails':['Never invent missing metrics.','Never claim guaranteed price targets or returns.','Never fabricate followers, likes, comments or trading outcomes.','Never spam users or manufacture engagement.','Never use financial urgency to justify reckless calls.','If evidence is insufficient, improve research instead of forcing a post.'],
  'next_action':'Use this decision layer before the next production cycle and feed its priorities into Creator Brain.'
 }
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False),encoding='utf-8')
 STATE.write_text(json.dumps({'last_run':decision,'cooldowns':cooldown},indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','priority_actions':len(priorities),'missing_inputs':missing,'next_action':decision['next_action']},ensure_ascii=False))
if __name__=='__main__':main()
