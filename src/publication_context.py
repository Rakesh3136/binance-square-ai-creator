"""Lock the production-cycle identity selected before engagement mutation."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/publication_context.json'
def load(rel):
    p=ROOT/rel
    if not p.exists(): return {}
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean(v): return str(v or '').upper().replace('USDT','').strip()
def main():
    frozen=load('data/live/authoritative_opportunity.json')
    brain=load('data/live/creator_brain_decision.json')
    pre=load('data/live/editorial_preflight.json')
    engagement=pre.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}
    symbol=clean(frozen.get('symbol')) or clean(brain.get('symbol')) or clean((pre.get('selected_opportunity') or {}).get('symbol'))
    if not symbol: raise SystemExit('No authoritative publication symbol')
    if frozen and clean(brain.get('symbol')) and symbol != clean(brain.get('symbol')): raise SystemExit(f'Asset drift detected: frozen={symbol}, brain={clean(brain.get("symbol"))}')
    category=str(frozen.get('category') or (pre.get('selected_opportunity') or {}).get('category') or 'market_opportunity')
    visual_decision={**(brain.get('visual_decision') or {})}
    # Autonomous market posts are always published with the real TradingView
    # visual. Never let an AI/editorial format downgrade a market post to text.
    visual_decision.update({'type':'candlestick_chart','use_visual':True,'required':True,'provider':'TradingView','timeframe':'1H'})
    context={'version':3,'locked_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'symbol_usdt':symbol+'USDT','category':category,'opportunity_score':float(frozen.get('score',0) or 0),'reason':str(frozen.get('reason') or brain.get('reason') or ''),'instruction':str(frozen.get('instruction') or ''),'editorial_format':str(brain.get('editorial_format') or experiment.get('format') or 'CHOICE'),'conversation_goal':str(brain.get('conversation_goal') or 'reply'),'experiment_id':str(engagement.get('experiment_id') or ''),'experiment_format':str(experiment.get('format') or brain.get('editorial_format') or ''),'market_phase':str(brain.get('market_phase') or 'UNKNOWN'),'visual_decision':visual_decision,'source':'frozen preflight opportunity + Creator Brain','guardrail':'The frozen opportunity is authoritative. No downstream stage may change the primary asset. TradingView is mandatory for autonomous market publication.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(context,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(context,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
