from pathlib import Path
import json
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
FILES={'audience':'data/intelligence/audience_profile.json','experiments':'data/intelligence/experiment_queue.json','timing':'data/intelligence/market_timing.json','visual':'data/intelligence/visual_decision.json','thesis':'data/intelligence/thesis_ledger.json','strategy':'analytics/strategy_memory.json','stories':'data/intelligence/story_memory.json','patterns':'data/intelligence/creator_patterns.json'}
OUT=ROOT/'data/live/creator_evolution_state.json'
def read(rel):
 p=ROOT/rel
 try:
  x=json.loads(p.read_text()); return x if isinstance(x,dict) else {}
 except:return {}
def main():
 d={k:read(v) for k,v in FILES.items()}
 audience=d['audience'].get('signals',{})
 try: sample=int(d['audience'].get('sample_size',0) or 0)
 except: sample=0
 phase='phase_1_foundation' if sample<10 else 'phase_2_experimentation' if sample<30 else 'phase_3_optimization' if sample<75 else 'phase_4_mature_creator'
 policies={
  'phase_1_foundation':['collect verified performance','avoid unsupported conclusions'],
  'phase_2_experimentation':['test different hooks/formats/questions','compare normalized engagement rates'],
  'phase_3_optimization':['promote repeat winners only after sufficient samples','retire persistent losers','optimize timing and follower conversion'],
  'phase_4_mature_creator':['maintain recurring stories and creator identity','balance proven formats with controlled exploration','revisit theses and disclose outcomes','optimize attention, conversation, followers and eligible attribution']}
 state={'version':2,'updated_at':datetime.now(timezone.utc).isoformat(),'phase':phase,'verified_sample_size':sample,'modules':list(FILES),'audience':audience,'learning_policy':{'promote_winners':sample>=30,'retire_repeated_failures':sample>=30,'test_unproven_formats':True,'optimize_posting_time':sample>=30,'optimize_monetization':sample>=30,'segment_audience_when_data_allows':sample>=75,'never_fabricate_metrics':True,'phase_actions':policies[phase]},'decision_priority':['verified opportunity','audience conversion','conversation quality','novelty','visual proof','monetization attribution','posting timing'],'revenue_policy':'Optimize for eligible genuine engagement and attribution, never fabricate trades, clicks, revenue, or follower growth.','warning':None if sample else 'Waiting for verified performance data; no winner is promoted yet.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)); print(json.dumps(state))
if __name__=='__main__': main()
