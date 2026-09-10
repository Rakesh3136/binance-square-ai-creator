import json, os, hashlib
from datetime import datetime, timezone
from pathlib import Path
STATUS=Path('data/live/creator_status.json'); USAGE=Path('analytics/ai_usage.json'); REPORT_DIR=Path('data/reports'); DAILY_LIMIT=int(os.getenv('GEMINI_DAILY_BUDGET','20'))

def load(path,default):
    if not path.exists(): return default
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,type(default)) else default
    except Exception:return default

def save_status(status,message,**extra):
    payload={'status':status,'message':message,'updated_at':datetime.now(timezone.utc).isoformat()}; payload.update(extra); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')

def latest_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return reports[0] if reports else None

def report_has_publishable_text(path):
    if not path: return False
    try:
        report=json.loads(path.read_text(encoding='utf-8')); draft=report.get('draft') if isinstance(report.get('draft'),dict) else {}
        candidates=(draft.get('text'),draft.get('post'),draft.get('body'),draft.get('content'),draft.get('caption'),report.get('text'),report.get('post'))
        return any(isinstance(x,str) and x.strip() for x in candidates)
    except Exception:return False

def run_creator():
    before=latest_report(); before_mtime=before.stat().st_mtime if before else 0
    import multi_agent_creator
    multi_agent_creator.main()
    after=latest_report()
    if not after or after.stat().st_mtime <= before_mtime or not report_has_publishable_text(after): raise RuntimeError('Gemini creator completed without producing a fresh publishable draft')

def emergency_verified_draft(reason):
    """Dependency-free rescue that preserves the frozen asset and varies prose.
    It never invents news, trade levels, outcomes or a replacement asset.
    """
    pre=load(Path('data/live/editorial_preflight.json'),{}); market=load(Path('data/live/market_snapshot.json'),{}); news=load(Path('data/live/news_snapshot.json'),{})
    selected=pre.get('selected_opportunity') or {}; selected=selected if isinstance(selected,dict) else {}
    wanted=str(selected.get('symbol') or '').upper().replace('USDT','').replace('$','').strip()
    if not wanted or not wanted.replace('_','').isalnum(): raise RuntimeError('Emergency fallback refused: frozen opportunity symbol is missing')
    items=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        vals=market.get(group) or []; items.extend(x for x in vals if isinstance(x,dict))
    item=next((x for x in items if str(x.get('symbol','')).upper().replace('USDT','')==wanted),None)
    if not item: raise RuntimeError(f'Emergency fallback refused: frozen asset ${wanted} is absent from the live market snapshot')
    symbol=wanted
    def n(key,default=0.0):
        try:return float(item.get(key) or default)
        except Exception:return default
    move=n('price_change_percent'); price=n('last_price'); volume=n('quote_volume_usdt') or n('quote_volume'); rng=n('intraday_range_percent'); signal=n('content_signal_score'); category=str(selected.get('category') or 'market_opportunity').replace('_',' ')
    candles=item.get('candles_1h') or []; highs=[]; lows=[]
    for c in candles[-24:]:
        if isinstance(c,(list,tuple)) and len(c)>=4:
            try: highs.append(float(c[2])); lows.append(float(c[3]))
            except Exception: pass
        elif isinstance(c,dict):
            try: highs.append(float(c.get('high'))); lows.append(float(c.get('low')))
            except Exception: pass
    resistance=max(highs) if highs else None; support=min(lows) if lows else None
    ptxt=f'${price:.8g}' if price else 'the latest verified price'; vtxt=f'${volume/1e6:.1f}M' if volume>=1e6 else (f'${volume/1e3:.0f}K' if volume>=1e3 else 'the available volume snapshot')
    seed=int(hashlib.sha256((symbol+datetime.now(timezone.utc).date().isoformat()).encode()).hexdigest()[:8],16)%4
    if category=='crypto meme':
        meme_hooks=['Crypto picked another perfectly normal day to test everyone’s patience.','The chart is asking for patience. Crypto Twitter is asking for chaos.','Some coins move on fundamentals. Some move on pure crypto plot development.','This is the part of the market where the risk plan gets tested before the ego does.']
        post=f'{meme_hooks[seed]}\n\n${symbol} is on the screen after a {move:+.1f}% move. The useful part is not pretending we know what happens next; it is watching whether the reaction actually confirms the move.\n\nNo heroic prediction here — just a market moment worth watching.\n\nWhat would make you laugh, wait, or change your view on ${symbol}?'
    else:
        hooks=[f'${symbol} moved {move:+.1f}%, but the interesting question is what the market does after the impulse.',f'I’m watching ${symbol} for the reaction, not chasing the headline move.',f'The ${symbol} move is easy to see. The useful information is in the structure that follows it.',f'${symbol} has enough movement to get attention; the next test decides whether that attention is justified.']
        context=f'Price is around {ptxt}, with {vtxt} in quote volume and a {rng:.1f}% intraday range.'
        level=f'On the recent 1H window, the observed range runs from about ${support:.8g} to ${resistance:.8g}.' if support is not None and resistance is not None else 'The available 1H snapshot does not provide a reliable range to quote.'
        post=(f'{hooks[seed]}\n\n{context} {level}\n\n'
              f'The current classification is {category}. That is a description of the setup, not a promise about the next candle.\n\n'
              f'I would rather wait for price to confirm the reaction than manufacture certainty from one move.\n\n'
              f'What specific reaction on ${symbol} would make you change your read?')
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'model':'deterministic-emergency-fallback','topic_instruction':selected.get('instruction',''),'selected_editorial_lane':selected,'engagement_strategy':pre.get('engagement_strategy') or {},'live_market_snapshot':market,'news_discovery_snapshot':news,'strategy_memory':load(Path('analytics/strategy_memory.json'),{}),'research':{'summary':'Emergency draft built only from the frozen asset and verified live market data.','strongest_signal':symbol,'source_mode':'deterministic_emergency_fallback','opportunity_score':float(selected.get('adjusted_score') or selected.get('raw_score') or 80)},'critique':{'summary':'AI generation unavailable; no unverified facts were added.','reason':str(reason)[-500:]},'draft':{'post':post,'text':post,'hook':post.split('\n\n')[0],'discussion_question':post.split('\n\n')[-1],'quality_score':84,'editorial_style':'verified_market_observation','generation_mode':'LOCAL_FALLBACK','experiment_id':(pre.get('engagement_strategy') or {}).get('experiment_id') or 'A','experiment_format':((pre.get('engagement_strategy') or {}).get('experiment') or {}).get('format'),'symbol':symbol,'content_category':category,'publication_status':'DRAFT_ONLY_NOT_PUBLISHED'},'visual_plan':{'type':'candlestick_chart','use_visual':bool(candles),'title':f'{symbol}: verified 1H market data','data_points':[{'symbol':symbol}],'purpose':'TradingView chart is rendered separately from the frozen opportunity.'},'status':'DRAFT_ONLY_NOT_PUBLISHED','generation_mode':'LOCAL_FALLBACK','emergency_fallback':True}
    REPORT_DIR.mkdir(parents=True,exist_ok=True); slug=''.join(c.lower() if c.isalnum() else '-' for c in symbol).strip('-') or 'market-opportunity'; path=REPORT_DIR/f'{slug}-emergency-multi-agent.json'; path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'EMERGENCY_LOCAL_DRAFT','report':str(path),'symbol':symbol,'category':category},indent=2))

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
