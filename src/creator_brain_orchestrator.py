from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/creator_brain_decision.json'

def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8'))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def main():
    pre=load(ROOT/'data/live/editorial_preflight.json')
    market=load(ROOT/'data/live/market_snapshot.json')
    news=load(ROOT/'data/live/news_snapshot.json')
    strategy=load(ROOT/'analytics/strategy_memory.json')
    patterns=load(ROOT/'data/intelligence/creator_patterns.json')
    stories=load(ROOT/'data/intelligence/story_memory.json')
    perf=load(ROOT/'analytics/post_metrics.json')
    recent=perf.get('recent_posts',[]) if isinstance(perf,dict) else []
    zero=max((p for p in recent if isinstance(p,dict)),key=lambda p: p.get('views',0),default={})
    no_reply=bool(zero) and (zero.get('replies',0) or zero.get('comments',0))==0
    exp=(pre.get('engagement_strategy') or {}).get('experiment') or {}
    decision={
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'objective':'attention_to_conversation_to_followers_to_eligible_monetization',
      'audience_signal':{'recent_high_view_no_reply':no_reply,'sample_size':len(recent)},
      'editorial_memory':{'active_stories':stories.get('active_stories',[])[:6],'recent_opinions':stories.get('recent_opinions',[])[:6]},
      'market_lanes':['top_gainers','top_losers','highest_volume','new_listing_market','top_content_signals'],
      'fresh_news_available':len(news.get('articles') or [])>0,
      'benchmark_patterns_available':bool(patterns),
      'current_experiment':{'id':pre.get('engagement_strategy',{}).get('experiment_id'),'format':exp.get('format')},
      'decision':{
        'avoid_repeating_last_format':no_reply,
        'prefer_conversation_format':True,
        'prefer_new_story_or_update':True,
        'require_original_angle':True,
        'require_verified_market_facts':True,
        'require_one_low_friction_question':True
      },
      'next_angle_priority':['CHART CHALLENGE','CHOICE','COIN VS COIN','DATA SURPRISE','NEWS REACTION','LIQUIDATION STORY']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'OK','output':str(OUT),'no_reply_signal':no_reply}))

if __name__=='__main__': main()
