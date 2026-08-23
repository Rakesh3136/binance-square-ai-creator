from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
PATHS={
'market':'data/live/market_snapshot.json','news':'data/live/news_snapshot.json','preflight':'data/live/editorial_preflight.json','strategy':'analytics/strategy_memory.json','patterns':'data/intelligence/creator_patterns.json','stories':'data/intelligence/story_memory.json','audience':'data/intelligence/audience_profile.json','experiments':'data/intelligence/experiment_queue.json','timing':'data/intelligence/market_timing.json','visual':'data/intelligence/visual_decision.json','thesis':'data/intelligence/thesis_ledger.json','evolution':'data/live/creator_evolution_state.json'}
OUT=ROOT/'data/live/creator_brain_decision.json'

def read(rel):
    try:
        x=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    d={k:read(v) for k,v in PATHS.items()}; market=d['market']; news=d['news']; preflight=d['preflight']; strategy=d['strategy']; patterns=d['patterns']; stories=d['stories']; audience=d['audience']; experiments=d['experiments']; timing=d['timing']; visual=d['visual']; thesis=d['thesis']; evolution=d['evolution']
    engagement=preflight.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}
    recent=(strategy.get('recent_observations') or [])[-20:]; passive=[x for x in recent if float(x.get('views',x.get('viewCount',0)) or 0)>0 and float(x.get('replies',x.get('replyCount',0)) or 0)==0 and float(x.get('followers_gained',0) or 0)==0]
    active=stories.get('active_stories') or []; used=[str(x.get('symbol','')).upper() for x in recent if x.get('symbol')]
    candidates=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and x.get('symbol'): candidates.append(x)
    candidates=sorted(candidates,key=lambda x:float(x.get('content_signal_score',0) or 0)+abs(float(x.get('price_change_percent',0) or 0)),reverse=True)
    # Prefer an opportunity not recently repeated and not classified as overheated unless shock/news value is strong.
    timing_map={str(x.get('symbol','')).upper().replace('USDT',''):x for x in timing.get('items',[]) if isinstance(x,dict)}
    chosen=next((x for x in candidates if str(x.get('symbol')).upper() not in used[:5] and timing_map.get(str(x.get('symbol')).upper().replace('USDT',''),{}).get('phase')!='OVERHEATED_OR_SHOCK'),None) or (candidates[0] if candidates else {})
    symbol=str(chosen.get('symbol','')).upper().replace('USDT','')
    formats=['CHOICE','CHART CHALLENGE','COIN VS COIN','DATA SURPRISE','BREAKOUT OR FAKEOUT','NEWS REACTION','LIQUIDATION STORY','TOP MOVERS']
    current=str(experiment.get('format') or 'CHOICE').upper(); queue=[x.get('format') for x in experiments.get('queue',[]) if isinstance(x,dict) and x.get('status')=='READY']; pool=[f for f in queue+formats if f]
    next_format=next((f for f in pool if f!=current),current) if passive else (current if current in pool else formats[0])
    audience_signals=audience.get('signals') or {}
    reply_rate=float(audience_signals.get('replies_per_view',0) or 0); like_rate=float(audience_signals.get('likes_per_view',0) or 0)
    decision={'generated_at':datetime.now(timezone.utc).isoformat(),'decision':'CREATE_ORIGINAL_EXPERIMENT','phase':evolution.get('phase','mature_creator'),'symbol':symbol,'editorial_format':next_format,'conversation_goal':'reply' if passive or reply_rate<0.005 else 'meaningful_engagement','story_continuity':bool(active),'avoid_recent_symbols':used[:5],'market_phase':timing_map.get(symbol,{}).get('phase','UNKNOWN'),'visual_decision':visual,'audience_signals':audience_signals,'experiment_queue':experiments.get('queue',[])[:12],'thesis_context':thesis.get('theses',[])[-10:],'reason':'Passive reach detected: change interaction mechanism and test a new format.' if passive else 'Use the strongest verified opportunity while balancing novelty and audience conversion.','research_inputs':{'market_candidates':len(candidates),'fresh_news':len(news.get('articles') or []),'active_stories':len(active)},'optimization_policy':evolution.get('learning_policy',{}),'benchmark_patterns':patterns,'story_context':stories,'learning_context':{'recent_observations':recent,'passive_recent_count':len(passive)},'guardrails':['Never invent facts.','Never copy another creator.','Never fabricate performance or revenue.','Use real market data only.','Promote winners only after verified samples.','Retire repeated failures only after enough observations.','Optimize for genuine engagement and eligible attribution, never artificial activity.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False)); print(json.dumps({'status':'OK','symbol':symbol,'editorial_format':next_format,'passive_recent_count':len(passive)}))
if __name__=='__main__':main()
