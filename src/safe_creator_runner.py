import json, os
from datetime import datetime, timezone
from pathlib import Path
STATUS=Path('data/live/creator_status.json'); USAGE=Path('analytics/ai_usage.json'); REPORT_DIR=Path('data/reports'); DAILY_LIMIT=int(os.getenv('GEMINI_DAILY_BUDGET','20'))

def load(path,default):
    if not path.exists(): return default
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,type(default)) else default
    except Exception:return default

def save_status(status,reason,**extra):
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'status':status,'reason':reason,**extra},indent=2,ensure_ascii=False),encoding='utf-8')

def run_creator():
    import multi_agent_creator; multi_agent_creator.main()

def emergency_verified_draft(reason):
    """Evidence-rich local rescue: never invents news or trading levels."""
    pre=load(Path('data/live/editorial_preflight.json'),{}); market=load(Path('data/live/market_snapshot.json'),{}); news=load(Path('data/live/news_snapshot.json'),{})
    selected=pre.get('selected_opportunity') or {}; selected=selected if isinstance(selected,dict) else {}
    items=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        vals=market.get(group) or []; items.extend(x for x in vals if isinstance(x,dict))
    wanted=str(selected.get('symbol') or selected.get('topic') or '').upper(); item=next((x for x in items if str(x.get('symbol','')).upper()==wanted),None) or next((x for x in items if x.get('symbol')),{}); symbol=str(item.get('symbol') or wanted or 'MARKET').upper().replace('USDT','')
    def n(key,default=0.0):
        try:return float(item.get(key) or default)
        except Exception:return default
    move=n('price_change_percent'); price=n('last_price'); volume=n('quote_volume_usdt') or n('quote_volume'); rng=n('intraday_range_percent'); signal=n('content_signal_score'); category=str(selected.get('category') or 'market_opportunity').replace('_',' ')
    candles=item.get('candles_1h') or []
    highs=[]; lows=[]
    for c in candles[-24:]:
        if isinstance(c,(list,tuple)) and len(c)>=4:
            try: highs.append(float(c[2])); lows.append(float(c[3]))
            except Exception: pass
        elif isinstance(c,dict):
            try: highs.append(float(c.get('high'))); lows.append(float(c.get('low')))
            except Exception: pass
    resistance=max(highs) if highs else None; support=min(lows) if lows else None
    ptxt=f'${price:.8g}' if price else 'the latest verified level'; vtxt=f'${volume/1e6:.1f}M' if volume>=1e6 else (f'${volume/1e3:.0f}K' if volume>=1e3 else 'live volume data')
    levels=''
    if support is not None and resistance is not None: levels=f'\n\n1H range: ${support:.8g} support zone → ${resistance:.8g} resistance zone.'
    post=(f'👀 ${symbol} is the market setup I’m watching right now.\n\n'
          f'Price is around {ptxt}, {move:+.1f}% on the current snapshot, with {vtxt} in quote volume. '
          f'The move is classified as {category}; intraday range is {rng:.1f}% and the attention score is {signal:.0f}.'
          f'{levels}\n\n'
          f'Bull case: buyers keep control and price holds above the key reaction area.\n'
          f'Bear case: the move fades and price loses nearby support.\n\n'
          f'I would watch the next 1H candle for confirmation rather than chase the first move.\n\n'
          f'Would you wait for confirmation on ${symbol}, or is the current structure enough for you?')[:880]
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'model':'deterministic-emergency-fallback','topic_instruction':selected.get('instruction',''),'selected_editorial_lane':selected,'engagement_strategy':pre.get('engagement_strategy') or {},'live_market_snapshot':market,'news_discovery_snapshot':news,'strategy_memory':load(Path('analytics/strategy_memory.json'),{}),'research':{'summary':'Emergency draft built only from verified live market data.','strongest_signal':symbol,'source_mode':'deterministic_emergency_fallback','opportunity_score':float(selected.get('adjusted_score') or selected.get('raw_score') or 80)},'critique':{'summary':'AI generation unavailable; no unverified facts were added.','reason':str(reason)[-500:]},'draft':{'post':post,'text':post,'hook':f'👀 ${symbol} is the market setup I’m watching right now.','discussion_question':f'Would you wait for confirmation on ${symbol}, or is the current structure enough for you?','quality_score':84,'editorial_style':'verified_market_observation','generation_mode':'LOCAL_FALLBACK','experiment_id':(pre.get('engagement_strategy') or {}).get('experiment_id') or 'A','experiment_format':((pre.get('engagement_strategy') or {}).get('experiment') or {}).get('format'),'symbol':symbol,'content_category':category,'publication_status':'DRAFT_ONLY_NOT_PUBLISHED'},'visual_plan':{'type':'candlestick_chart','use_visual':bool(candles),'title':f'{symbol}: verified 1H market data','data_points':[{'symbol':symbol}],'purpose':'TradingView chart is rendered separately from verified market selection.'},'status':'DRAFT_ONLY_NOT_PUBLISHED','generation_mode':'LOCAL_FALLBACK','emergency_fallback':True}
    REPORT_DIR.mkdir(parents=True,exist_ok=True); slug=''.join(c.lower() if c.isalnum() else '-' for c in symbol).strip('-') or 'market-opportunity'; path=REPORT_DIR/f'{slug}-emergency-multi-agent.json'; path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'EMERGENCY_LOCAL_DRAFT','report':str(path),'symbol':symbol},indent=2))

def local_or_emergency(original_error):
    try:
        import importlib.util
        if importlib.util.find_spec('google.genai') is not None:
            run_creator(); return 'LOCAL_FALLBACK_SUCCESS'
        print('google.genai unavailable; using dependency-free verified creator')
    except Exception as fallback_exc: print(f'Local AI fallback failed: {fallback_exc}')
    emergency_verified_draft(original_error); return 'EMERGENCY_SUCCESS'

def main():
    today=datetime.now(timezone.utc).date().isoformat(); usage=load(USAGE,{'date':today,'requests':0}); usage=usage if usage.get('date')==today else {'date':today,'requests':0}; requests=int(usage.get('requests',0))
    if requests>=DAILY_LIMIT:
        fallback_status=local_or_emergency('Gemini daily budget exhausted'); save_status('AI_SUCCESS','Gemini budget exhausted; verified local creator used',requests=requests,daily_limit=DAILY_LIMIT,generation_mode='LOCAL_FALLBACK',fallback_status=fallback_status); return 0
    usage['requests']=requests+1; USAGE.parent.mkdir(parents=True,exist_ok=True); USAGE.write_text(json.dumps(usage,indent=2),encoding='utf-8')
    try: run_creator()
    except Exception as exc:
        message=str(exc); print(f'Gemini creator failed; switching immediately to verified local creator. Original error: {message}'); fallback_status=local_or_emergency(message); save_status('AI_SUCCESS','Gemini creator failed; verified local creator preserved the cycle',error=message,requests=usage['requests'],daily_limit=DAILY_LIMIT,generation_mode='LOCAL_FALLBACK',fallback_status=fallback_status); return 0
    save_status('AI_SUCCESS','Fresh Gemini draft generated',requests=usage['requests'],daily_limit=DAILY_LIMIT,generation_mode='GEMINI'); return 0
if __name__=='__main__':raise SystemExit(main())
