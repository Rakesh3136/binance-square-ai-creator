from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data/live/market_snapshot.json'
NEWS=ROOT/'data/live/news_snapshot.json'
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
STRATEGY=ROOT/'analytics/strategy_memory.json'
PATTERNS=ROOT/'data/intelligence/creator_patterns.json'
STORIES=ROOT/'data/intelligence/story_memory.json'
OUT=ROOT/'data/live/creator_brain_decision.json'


def read(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}


def main():
    market,news,preflight,strategy,patterns,stories=map(read,[LIVE,NEWS,PREFLIGHT,STRATEGY,PATTERNS,STORIES])
    engagement=preflight.get('engagement_strategy') or {}
    experiment=engagement.get('experiment') or {}
    recent=(strategy.get('recent_observations') or [])[-12:]
    failed=[x for x in recent if float(x.get('replies',0) or 0)==0 and float(x.get('followers_gained',0) or 0)==0]
    active=stories.get('active_stories') or []
    used_symbols=[str(x.get('symbol','')).upper() for x in recent if x.get('symbol')]
    candidates=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(group) or []:
            if isinstance(x,dict) and x.get('symbol'):
                candidates.append(x)
    candidates=sorted(candidates,key=lambda x:float(x.get('content_signal_score',0) or x.get('price_change_percent',0) or 0),reverse=True)
    chosen=next((x for x in candidates if str(x.get('symbol')).upper() not in used_symbols[:3]), candidates[0] if candidates else {})
    symbol=str(chosen.get('symbol','')).upper().replace('USDT','')
    formats=['CHOICE','CHART CHALLENGE','COIN VS COIN','DATA SURPRISE','BREAKOUT OR FAKEOUT','NEWS REACTION','LIQUIDATION STORY','TOP MOVERS']
    current=str(experiment.get('format') or 'CHOICE').upper()
    # If recent outcomes are passive, deliberately change interaction mechanism.
    next_format=next((f for f in formats if f != current), current) if failed else current
    decision={
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'decision':'CREATE_ORIGINAL_EXPERIMENT',
      'symbol':symbol,
      'editorial_format':next_format,
      'conversation_goal': 'reply' if failed else 'meaningful_engagement',
      'story_continuity': bool(active),
      'avoid_recent_symbols':used_symbols[:3],
      'reason': 'Recent passive posts require a different interaction mechanism.' if failed else 'Continue the current experiment while market opportunity remains strong.',
      'research_inputs':{'market_candidates':len(candidates),'fresh_news':len(news.get('articles') or []),'active_stories':len(active)},
      'benchmark_patterns':patterns,
      'story_context':stories,
      'learning_context':{'recent_observations':recent,'passive_recent_count':len(failed)},
      'guardrails':['Never invent facts.','Never copy another creator.','Never fabricate performance.','Use real market data only.','Do not repeat the same format when recent evidence is passive.']
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'OK','symbol':symbol,'editorial_format':next_format,'passive_recent_count':len(failed)}))

if __name__=='__main__': main()
