"""Lock the production-cycle identity and publication package before AI generation."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/live/publication_context.json'
def load(rel):
    p=ROOT/rel
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean(v): return str(v or '').upper().replace('USDT','').replace('$','').strip()
def main():
    frozen=load('data/live/authoritative_opportunity.json'); brain=load('data/live/creator_brain_decision.json'); pre=load('data/live/editorial_preflight.json'); news=load('data/live/news_snapshot.json')
    engagement=pre.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}; selected=pre.get('selected_opportunity') or {}
    symbol=clean(frozen.get('symbol')) or clean(brain.get('symbol')) or clean(selected.get('symbol'))
    if not symbol: raise SystemExit('No authoritative publication symbol')
    if frozen and clean(brain.get('symbol')) and symbol!=clean(brain.get('symbol')): raise SystemExit(f'Asset drift detected: frozen={symbol}, brain={clean(brain.get("symbol"))}')
    category=str(frozen.get('category') or selected.get('category') or 'market_opportunity').lower(); fmt=str(brain.get('editorial_format') or experiment.get('format') or 'CHOICE').upper()
    selected_title=str(selected.get('news_title') or '').strip(); chart_symbols=[]
    for article in news.get('articles') or []:
        if not isinstance(article,dict): continue
        if selected_title and str(article.get('title') or '').strip()!=selected_title: continue
        for x in article.get('symbols') or []:
            s=clean(x)
            if s and s not in chart_symbols: chart_symbols.append(s)
        break
    if not chart_symbols: chart_symbols=[symbol]
    if symbol not in chart_symbols: chart_symbols.insert(0,symbol)
    chart_symbols=chart_symbols[:2]
    major_news=bool(selected_title and category in {'breaking_news','news_and_macro','macro'})
    publication_mode='article' if major_news else 'image'
    visual_decision={**(brain.get('visual_decision') or {}),'type':'candlestick_chart','use_visual':True,'required':True,'provider':'TradingView','timeframe':'1H','chart_symbols':chart_symbols,'layout':'pair' if len(chart_symbols)>1 else 'single'}
    context={'version':5,'locked_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'symbol_usdt':symbol+'USDT','category':category,'opportunity_score':float(frozen.get('score',0) or 0),'reason':str(frozen.get('reason') or brain.get('reason') or ''),'instruction':str(selected.get('instruction') or frozen.get('instruction') or ''),'editorial_format':fmt,'conversation_goal':str(brain.get('conversation_goal') or 'reply'),'publication_mode':publication_mode,'article_title':selected_title[:180] if major_news else '', 'news_title':selected_title[:240], 'news_source':str(selected.get('news_source') or ''),'chart_symbols':chart_symbols,'experiment_id':str(engagement.get('experiment_id') or experiment.get('id') or ''),'experiment_format':str(experiment.get('format') or fmt),'experiment_hook':str(experiment.get('hook') or ''),'experiment_question':str(experiment.get('question') or ''),'market_phase':str(brain.get('market_phase') or 'UNKNOWN'),'visual_decision':visual_decision,'content_coverage':engagement.get('content_coverage') or [],'style_rule':str(engagement.get('style_rule') or ''),'hook_rule':str(engagement.get('hook_rule') or ''),'question_rule':str(engagement.get('question_rule') or ''),'writing_rule':str(engagement.get('writing_rule') or ''),'technical_rule':str(engagement.get('technical_rule') or ''),'creator_tracking_rule':str(engagement.get('creator_tracking_rule') or ''),'growth_rule':str(engagement.get('growth_rule') or ''),'monetization_rule':str(engagement.get('monetization_rule') or ''),'source':'frozen opportunity + Creator Brain + engagement strategy + fresh news','guardrail':'Frozen primary asset is authoritative. TradingView is mandatory. News articles must preserve verified source context. Publication mode is chosen from story importance, not a fixed template.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(context,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(context,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
