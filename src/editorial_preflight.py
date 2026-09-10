import json,re,subprocess,sys
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
MARKET=Path('data/live/market_snapshot.json');NEWS=Path('data/live/news_snapshot.json');MEMORY=Path('analytics/strategy_memory.json');PUBLICATIONS=Path('analytics/publication_log.jsonl');FEEDBACK=Path('data/live/feedback_strategy.json');FLOW=Path('data/live/capital_flow_intelligence.json');RESEARCH=Path('data/live/original_research.json');OUTPUT=Path('data/live/editorial_preflight.json')
MIN_MARKET_SCORE=72.0;NEWS_FRESH_MINUTES=180;NEWS_MATERIAL_SCORE=45.0;MEMORY_REPEAT_PENALTY=18.0;MEMORY_HARD_BLOCK_COUNT=3;CATEGORY_REPEAT_PENALTY=14.0;ASSET_COOLDOWN_HOURS=12;FLOW_MIN_CONFIDENCE=65.0

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def rows(v):return v if isinstance(v,list) else []
def num(v,d=0.0):
    try:return float(v)
    except Exception:return d
def clamp(v,lo=0.0,hi=100.0):return round(max(lo,min(hi,num(v))),2)
def norm(v):return str(v or '').upper().replace('USDT','').replace('$','').replace('BINANCE:','').strip()
def extract_symbols(t):
    found=set();blob=str(t or '').upper()
    for token in re.findall(r'(?<![A-Z0-9])\$?[A-Z][A-Z0-9]{0,11}(?:USDT)?(?![A-Z0-9])',blob):
        b=token.replace('$','');b=b[:-4] if b.endswith('USDT') else b
        if 1<=len(b)<=10:found.add(b)
    if 'GOLD' in blob:found.add('XAUUSD')
    if 'SILVER' in blob:found.add('XAGUSD')
    return found

def recent_publications():
    out=[];cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    if not PUBLICATIONS.exists():return out
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines():
        try:
            row=json.loads(line);dt=datetime.fromisoformat(str(row.get('published_at','')).replace('Z','+00:00'))
            if dt>=cutoff:out.append({**row,'_symbols':extract_symbols(' '.join(str(row.get(k) or '') for k in ('symbol','selected_lane_symbol','topic'))),'_dt':dt})
        except Exception:pass
    return out

def add_market(pool,cat,item,boost=0,research_item=None):
    if not isinstance(item,dict) or not item.get('symbol'):return
    move=abs(num(item.get('price_change_percent')));vol=num(item.get('quote_volume_usdt') or item.get('quote_volume'));signal=num(item.get('content_signal_score'));rng=num(item.get('intraday_range_percent'))
    raw=clamp(signal)
    if cat in {'top_gainers','top_losers'}:raw=clamp(move*3.2+rng*.6+signal*.35)
    elif cat=='volume_leaders':raw=clamp(signal*.45+min(35,(vol/1e8)*35)+min(15,rng*.5))
    elif cat=='new_listings':raw=clamp(signal*.45+max(0,20-num(item.get('days_since_listing'),30)*2))
    if research_item:
        # Asset-specific research is more useful than the global mean, but missing
        # fundamental evidence reduces the score rather than creating false conviction.
        info=clamp(research_item.get('information_advantage_score'));under=clamp(research_item.get('undercoverage_score'));ev=clamp(research_item.get('evidence_score'));risk=clamp(research_item.get('risk_red_flag_score'));missing=len(rows(research_item.get('missing_evidence')))
        research_score=0.45*info+0.2*under+0.25*ev+0.1*(100-risk)-min(20,missing*2.5)
        raw=clamp(0.6*raw+0.4*research_score)
    pool.append({'type':'market','category':cat,'topic':str(item['symbol']).upper(),'raw_score':raw,'reason':cat,'price_change_percent':num(item.get('price_change_percent')),'quote_volume_usdt':vol,'intraday_range_percent':rng,'content_signal_score':signal,'has_1h_ohlcv':bool(item.get('candles_1h'))})

def add_news(pool,a,known_symbols=None):
    if not isinstance(a,dict):return
    title=str(a.get('title') or '').strip();pub=str(a.get('published_at') or '')
    try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(pub.replace('Z','+00:00'))).total_seconds()/60
    except Exception:return
    if not title or age < -10 or age > NEWS_FRESH_MINUTES:return
    score=clamp(a.get('news_score'))
    if score<NEWS_MATERIAL_SCORE:return
    syms=[norm(s) for s in (a.get('symbols') or []) if norm(s)] or list(extract_symbols(title+' '+str(a.get('summary') or '')))
    known=known_symbols or set()
    if known:syms=[s for s in syms if s in known]
    syms=[s for s in syms if re.fullmatch(r'[A-Z0-9]{1,10}',s)]
    # Never invent BTC (or any asset) for an unanchored headline. An unanchored
    # macro story can still be retained in diagnostics, but is not publishable as
    # an asset-tagged crypto story.
    if not syms:return
    pool.append({'type':'news','category':'breaking_news' if score>=70 else 'news_and_macro','topic':syms[0]+'USDT' if syms[0] not in {'XAUUSD','XAGUSD'} else syms[0],'symbol':syms[0],'raw_score':score,'reason':'fresh verified news catalyst','title':title[:240],'url':str(a.get('url') or ''),'source':str(a.get('source') or ''),'published_at':pub,'news_score':score,'news_symbols':syms[:2]})

def run_flow():
    try:
        proc=subprocess.run([sys.executable,'src/creator_23_0_capital_flow_intelligence.py'],capture_output=True,text=True,timeout=180)
        if proc.stdout:print(proc.stdout,end='')
        if proc.stderr:print(proc.stderr,end='',file=sys.stderr)
        return proc.returncode==0
    except Exception as exc:
        print(f'capital-flow engine unavailable: {type(exc).__name__}: {exc}',file=sys.stderr);return False

def main():
    flow_ok=run_flow();market,news,memory,flow,research=load(MARKET),load(NEWS),load(MEMORY),load(FLOW),load(RESEARCH)
    pubs=recent_publications();pc=Counter();cc=Counter();last={}
    for r in pubs:
        for s in r.get('_symbols',set()):pc[s]+=1;last[s]=max(last.get(s,datetime.min.replace(tzinfo=timezone.utc)),r['_dt'])
        if r.get('content_category'):cc[str(r['content_category']).lower()]+=1
    mc=Counter(norm(x.get('topic')) for x in rows(memory.get('recent_performance_observations')) if isinstance(x,dict) and x.get('topic'));pool=[]
    research_by={norm(x.get('symbol')):x for x in rows(research.get('potential_gems'))+rows(research.get('potential_risks')) if isinstance(x,dict) and x.get('symbol')}
    for cat,key,n in [('top_gainers','top_gainers',12),('top_losers','top_losers',12),('volume_leaders','highest_volume',12),('new_listings','new_listing_market',10)]:
        for x in rows(market.get(key))[:n]:add_market(pool,cat,x,research_item=research_by.get(norm(x.get('symbol'))))
    for x in sorted([z for z in rows(market.get('top_content_signals')) if isinstance(z,dict)],key=lambda z:num(z.get('intraday_range_percent')),reverse=True)[:10]:add_market(pool,'high_volatility',x,3,research_by.get(norm(x.get('symbol'))))
    known={norm(x.get('symbol')) for x in rows(market.get('top_content_signals'))+rows(market.get('top_gainers'))+rows(market.get('top_losers'))+rows(market.get('highest_volume'))+rows(market.get('new_listing_market')) if isinstance(x,dict) and x.get('symbol')}
    fresh=[]
    for a in rows(news.get('articles')):
        before=len(pool);add_news(pool,a,known)
        if len(pool)>before:fresh.append(pool[-1])
    flow_candidates=[]
    for a in rows(flow.get('top_conditional_setups')):
        if not isinstance(a,dict):continue
        s=norm(a.get('symbol'));setup=a.get('trade_setup') or {};side=str(setup.get('side') or 'WAIT').upper();m=a.get('multitimeframe') or {};conf=num(m.get('confidence') or a.get('confidence'))
        if not s or side not in {'LONG','SHORT'} or conf<FLOW_MIN_CONFIDENCE:continue
        raw=clamp(0.55*conf+0.25*num(m.get('flow_proxy_score'),50)+0.20*(50+abs(num(a.get('relative_strength_to_btc')))*5))
        flow_candidates.append({'type':'flow','category':'capital_flow_long' if side=='LONG' else 'capital_flow_short','topic':s+'USDT','symbol':s,'raw_score':raw,'reason':'multi-timeframe capital-flow rotation setup','flow_side':side,'flow_confidence':conf,'trade_setup':setup,'relative_strength_to_btc':a.get('relative_strength_to_btc'),'flow_proxy_score':m.get('flow_proxy_score'),'flow_notes':a.get('flow_notes') or []})
        if flow_candidates[-1]['trade_setup'].get('trigger') is None or flow_candidates[-1]['trade_setup'].get('invalidation') is None:flow_candidates[-1]['raw_score']=clamp(flow_candidates[-1]['raw_score']-10)
    pool.extend(flow_candidates);now=datetime.now(timezone.utc)
    for c in pool:
        base=norm(c.get('topic'));recent=pc.get(base,0);mem=mc.get(base,0);cat=cc.get(str(c.get('category')).lower(),0);active=bool(last.get(base) and now-last[base]<timedelta(hours=ASSET_COOLDOWN_HOURS));
        # No lane gets a free pass. News/flow may remain eligible, but repetition still
        # affects their score and a recent asset can be rejected.
        penalty=min(28,recent*8)+min(24,mem*8)+min(18,cat*6)+(20 if active else 0)
        c['adjusted_score']=clamp(num(c.get('raw_score'))-penalty);c['repeated']=recent>=3 or mem>=MEMORY_HARD_BLOCK_COUNT or active;c['cooldown_active']=active;c['recent_count']=recent;c['memory_count']=mem;c['category_recent_count']=cat
    news_candidates=[c for c in pool if c.get('type')=='news' and not c.get('repeated')];flow_candidates=[c for c in pool if c.get('type')=='flow' and not c.get('repeated')];market_candidates=[c for c in pool if c.get('type')=='market' and not c.get('repeated')]
    best_news=max(news_candidates,key=lambda x:x['adjusted_score'],default=None);best_flow=max(flow_candidates,key=lambda x:x['adjusted_score'],default=None);best_market=max(market_candidates,key=lambda x:x['adjusted_score'],default=None)
    finalists=[x for x in (best_news,best_flow,best_market) if x]
    best=max(finalists,key=lambda x:x['adjusted_score']) if finalists else None
    # Avoid publishing a weak candidate simply because something exists.
    run_ai=bool(best and num(best.get('adjusted_score'))>=MIN_MARKET_SCORE)
    reason='no_strong_opportunity'
    if best:reason={'news':'strong_news_opportunity','flow':'strong_capital_flow_opportunity','market':'strong_market_opportunity'}.get(best.get('type'),'strong_opportunity') if run_ai else 'candidate_below_publish_threshold'
    selected=None
    if run_ai:
        selected={'category':best['category'],'symbol':best['topic'],'reason':best['reason'],'recommended_experiment':None,'lane':best.get('type'),'score':best['adjusted_score'],'instruction':'Use the selected opportunity as authoritative. Add original interpretation and evidence; do not replace the selected asset with a generic mover.'}
        if best.get('type')=='news':selected.update({'news_title':best.get('title'),'news_url':best.get('url'),'news_source':best.get('source'),'news_published_at':best.get('published_at'),'news_score':best.get('news_score'),'news_symbols':best.get('news_symbols')})
        if best.get('type')=='flow':selected.update({'flow_side':best.get('flow_side'),'flow_confidence':best.get('flow_confidence'),'trade_setup':best.get('trade_setup'),'relative_strength_to_btc':best.get('relative_strength_to_btc'),'flow_proxy_score':best.get('flow_proxy_score'),'flow_notes':best.get('flow_notes')})
    top=sorted(pool,key=lambda x:num(x.get('adjusted_score')),reverse=True)[:40]
    result={'generated_at':now.isoformat(),'run_ai':run_ai,'reason':reason,'selected_opportunity':selected,'candidate_pool':top,'best_news_candidate':best_news,'best_flow_candidate':best_flow,'best_market_candidate':best_market,'capital_flow':{'engine_status':'OK' if flow_ok else 'UNAVAILABLE','market_regime':(flow.get('market_rotation') or {}).get('market_regime'),'btc_flow_proxy_score':(flow.get('market_rotation') or {}).get('btc_flow_proxy_score'),'leaders':(flow.get('market_rotation') or {}).get('leaders',[]),'laggards':(flow.get('market_rotation') or {}).get('laggards',[]),'tradeable_setups':len(rows(flow.get('top_conditional_setups')))},'fresh_news_count':len(fresh),'recent_topic_counts':dict(pc),'recent_category_counts':dict(cc),'memory_topic_counts':dict(mc),'rules':{'min_publish_score':MIN_MARKET_SCORE,'news_material_score':NEWS_MATERIAL_SCORE,'news_fresh_minutes':NEWS_FRESH_MINUTES,'asset_cooldown_hours':ASSET_COOLDOWN_HOURS,'flow_setup_min_confidence':FLOW_MIN_CONFIDENCE,'no_news_asset_fallback':True,'scores_bounded_0_100':True,'all_lanes_compete':True,'flow_is_conditional_not_predictive':True}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'OK','version':'7.0-opportunity-router','run_ai':run_ai,'reason':reason,'selected':selected,'top_candidates':[{"type":x.get("type"),"category":x.get("category"),"symbol":x.get("symbol"),"score":x.get("adjusted_score")} for x in top[:8]]},indent=2,ensure_ascii=False))
if __name__=='__main__':raise SystemExit(main())
