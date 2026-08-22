"""Distribution/timing layer: choose freshness and timing hypotheses, not fake engagement."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

PREFLIGHT=Path('data/live/editorial_preflight.json')
OUTPUT=Path('data/live/distribution_strategy.json')

TIMING_WINDOWS=['breaking_now','early_move','confirmation','post_event_reaction','evergreen']


def load(p):
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except Exception:return {}

def main():
    d=load(PREFLIGHT)
    selected=d.get('selected_opportunity') or d.get('best_market_candidate') or {}
    news=d.get('fresh_news_count',0)
    score=float(selected.get('adjusted_score') or selected.get('raw_score') or 0)
    category=str(selected.get('category') or selected.get('type') or 'market').lower()
    if news and ('news' in category or 'macro' in category): window='breaking_now'
    elif score>=90: window='early_move'
    elif score>=72: window='confirmation'
    else: window='evergreen'
    strategy={
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'timing_hypothesis':window,
      'priority':'freshness_over_fixed_schedule',
      'publish_rule':'publish when a verified opportunity is fresh and materially different; do not publish merely because a timer fired',
      'avoid':'stale recap after the main move has already happened',
      'distribution_tests':[
        'breaking_now vs confirmation',
        'short text+chart vs chart-led hook',
        'single asset vs comparison',
        'news reaction vs technical reaction'
      ],
      'measurement':['views','likes','replies','shares','followers_gained','eligible_monetization_signals'],
      'important_note':'Low views and zero engagement are separate diagnoses; do not infer causality from small samples.'
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(strategy,indent=2),encoding='utf-8')
    d['distribution_strategy']=strategy
    PREFLIGHT.write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(json.dumps(strategy,indent=2))

if __name__=='__main__':main()
