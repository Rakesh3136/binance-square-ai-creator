"""Lock the production-cycle identity and publication package before AI generation."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/publication_context.json'
def load(rel):
    p=ROOT/rel
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean(v): return str(v or '').upper().replace('USDT','').replace('$','').strip()
def main():
    frozen=load('data/live/authoritative_opportunity.json'); brain=load('data/live/creator_brain_decision.json'); pre=load('data/live/editorial_preflight.json'); director=load('data/live/content_director_brief.json')
    engagement=pre.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}; selected=pre.get('selected_opportunity') or {}
    symbol=clean(frozen.get('symbol')) or clean(brain.get('symbol')) or clean(selected.get('symbol'))
    if not symbol: raise SystemExit('No authoritative publication symbol')
    brain_symbol=clean(brain.get('symbol')); frozen_symbol=clean(frozen.get('symbol'))
    if frozen_symbol and brain_symbol and frozen_symbol!=brain_symbol: raise SystemExit(f'Asset drift detected: frozen={frozen_symbol}, brain={brain_symbol}')
    selected_title=str(selected.get('news_title') or '').strip()
    news_authoritative=bool(selected_title or frozen.get('news_title'))
    if selected.get('symbol') and clean(selected.get('symbol'))!=symbol and not news_authoritative:
        raise SystemExit(f'Asset drift detected: frozen={symbol}, selected={clean(selected.get("symbol"))}')
    category=str(frozen.get('category') or selected.get('category') or director.get('primary_story',{}).get('lane') or 'market_opportunity').lower()
    if news_authoritative: category='breaking_news'
    fmt=str(brain.get('editorial_format') or director.get('recommended_format') or experiment.get('format') or 'NEWS REACTION').upper()
    requested=[]
    for source_obj in (brain.get('visual_decision') or {}, director.get('visual_plan') or {}):
        for x in source_obj.get('chart_symbols') or source_obj.get('symbols') or []:
            s=clean(x)
            if s and s not in requested: requested.append(s)
    if category=='comparison':
        for x in (director.get('primary_story') or {}).get('chart_symbols') or []:
            s=clean(x)
            if s and s not in requested: requested.append(s)
    chart_symbols=[symbol]
    pair_requested=category=='comparison' or str((brain.get('visual_decision') or {}).get('layout') or '').lower()=='pair'
    if pair_requested:
        for s in requested:
            if s!=symbol: chart_symbols.append(s); break
    news_title=str(selected_title or frozen.get('news_title') or '').strip()
    news_source=str(selected.get('news_source') or frozen.get('news_source') or '').strip()
    major_news=bool(news_title)
    publication_mode='article' if major_news else 'image'
    visual_decision={**(brain.get('visual_decision') or {}),'type':'candlestick_chart','use_visual':True,'required':True,'provider':'TradingView','timeframe':'1H','chart_symbols':chart_symbols,'layout':'pair' if len(chart_symbols)>1 else 'single'}
    context={'version':5.4,'locked_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'symbol_usdt':symbol+'USDT','category':category,'opportunity_score':float(frozen.get('score',0) or 0),'reason':str(frozen.get('reason') or brain.get('reason') or ''),'instruction':str(selected.get('instruction') or frozen.get('instruction') or ''),'editorial_format':fmt,'story_engine':str(brain.get('story_engine') or director.get('narrative_engine') or 'NEWSROOM'),'conversation_goal':str(brain.get('conversation_goal') or 'specific_reply'),'publication_mode':publication_mode,'article_title':news_title[:180] if major_news else '', 'news_title':news_title[:240], 'news_source':news_source,'chart_symbols':chart_symbols,'experiment_id':str(engagement.get('experiment_id') or experiment.get('id') or ''),'experiment_format':str(experiment.get('format') or fmt),'experiment_hook':str(experiment.get('hook') or ''),'experiment_question':str(experiment.get('question') or ''),'market_phase':str(brain.get('market_phase') or 'UNKNOWN'),'visual_decision':visual_decision,'content_coverage':engagement.get('content_coverage') or [],'style_rule':str(engagement.get('style_rule') or ''),'hook_rule':str(engagement.get('hook_rule') or ''),'question_rule':str(engagement.get('question_rule') or ''),'writing_rule':str(engagement.get('writing_rule') or ''),'technical_rule':str(engagement.get('technical_rule') or ''),'creator_tracking_rule':str(engagement.get('creator_tracking_rule') or ''),'growth_rule':str(engagement.get('growth_rule') or ''),'monetization_rule':str(engagement.get('monetization_rule') or ''),'source':'frozen opportunity + Creator Brain + Content Director + engagement strategy + fresh news','guardrail':'Frozen primary asset is authoritative. Any selected news title makes the story authoritative news. TradingView is mandatory. Secondary charts are opt-in only for explicit comparison/pair decisions. No arbitrary fallback asset is added.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(context,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(context,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
