from pathlib import Path
import json
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
FILES={
'audience':'data/intelligence/audience_profile.json','experiments':'data/intelligence/experiment_queue.json','timing':'data/intelligence/market_timing.json','visual':'data/intelligence/visual_decision.json','thesis':'data/intelligence/thesis_ledger.json','strategy':'analytics/strategy_memory.json','stories':'data/intelligence/story_memory.json','patterns':'data/intelligence/creator_patterns.json'}
OUT=ROOT/'data/live/creator_evolution_state.json'
def read(rel):
 p=ROOT/rel
 try:return json.loads(p.read_text())
 except:return {}
def main():
 d={k:read(v) for k,v in FILES.items()}
 audience=d['audience'].get('signals',{})
 state={'version':1,'updated_at':datetime.now(timezone.utc).isoformat(),'phase':'mature_creator','modules':list(FILES),'audience':audience,'learning_policy':{'promote_winners':True,'retire_repeated_failures':True,'test_unproven_formats':True,'optimize_posting_time':True,'optimize_monetization':True,'segment_audience_when_data_allows':True,'never_fabricate_metrics':True},'decision_priority':['verified opportunity','audience conversion','conversation quality','novelty','visual proof','monetization attribution','posting timing'],'revenue_policy':'Optimize for eligible genuine engagement and attribution, never fabricate trades, clicks, revenue, or follower growth.'}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)); print(json.dumps(state))
if __name__=='__main__': main()
