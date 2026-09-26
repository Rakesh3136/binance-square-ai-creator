from __future__ import annotations
import json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / 'data/live/editorial_preflight.json'
ENGAGEMENT = ROOT / 'data/live/engagement_strategy.json'
MARKET = ROOT / 'data/live/market_snapshot.json'
CADENCE = ROOT / 'data/live/autonomous_cadence_6.json'
SIGNAL = ROOT / 'data/live/signal_first_routing.json'
PORTFOLIO = ROOT / 'data/live/content_portfolio_guard.json'
OUT = ROOT / 'data/live/authoritative_opportunity.json'
BASES = ['https://data-api.binance.vision', 'https://api-gcp.binance.com', 'https://api1.binance.com', 'https://api2.binance.com']

def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def symbol(v):
    if isinstance(v,dict):
        for k in ('symbol','selected_lane_symbol','topic'):
            raw=str(v.get(k) or '').upper().strip().replace('BINANCE:','')
            if raw: return raw if raw.endswith('USDT') else raw+'USDT'
    raw=str(v or '').upper().strip().replace('BINANCE:','')
    if not raw: return ''
    return raw if raw.endswith('USDT') else raw+'USDT'

def base_symbol(v):
    s=symbol(v)
    return s[:-4] if s.endswith('USDT') else s

def score(v):
    if not isinstance(v,dict): return 0.0
    for k in ('selected_score','effective_score','adjusted_score','portfolio_score','engagement_score','raw_score','opportunity_score','content_signal_score','news_score','score'):
        try:
            n=float(v.get(k) or 0)
            if math.isfinite(n) and n>0: return min(100.0,max(0.0,n))
        except Exception: pass
    return 0.0

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'binance-square-ai-creator/4.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as h: return json.loads(h.read().decode('utf-8'))

def trading_symbols():
    last=None
    for base in BASES:
        try:
            data=fetch(base+'/api/v3/exchangeInfo?symbolStatus=TRADING')
            symbols={str(x.get('symbol','')).upper() for x in data.get('symbols',[]) if str(x.get('status','')).upper()=='TRADING'}
            if symbols: return symbols
        except Exception as exc: last=exc
    raise RuntimeError(f'Unable to verify Binance trading symbols: {last}')

def add_candidate(pool,seen,value,source):
    if not isinstance(value,dict): return
    s=symbol(value)
    if not s or s in seen: return
    item=dict(value); item['_freeze_source']=source
    seen.add(s); pool.append(item)

def portfolio_candidates(portfolio):
    out=[]
    selected=portfolio.get('selected')
    if isinstance(selected,dict): out.append(('content_portfolio_guard_selected',selected))
    for x in portfolio.get('top_allowed_candidates') or []:
        if isinstance(x,dict):
            candidate=x.get('candidate') if isinstance(x.get('candidate'),dict) else x
            out.append(('content_portfolio_guard_ranked_fallback',candidate))
    return out

def signal_candidate(signal):
    if not isinstance(signal,dict) or signal.get('publish') is not True: return None
    selected=signal.get('selected')
    if not isinstance(selected,dict) or not symbol(selected): return None

    # The router is authoritative for BOTH trade and editorial lanes.  The old
    # freezer only understood complete trade contracts, which caused it to
    # discard a valid editorial selection and silently replace it with a
    # generic portfolio candidate.  Preserve the exact selected story here.
    if bool(selected.get('editorial_only')) or str(signal.get('decision') or '').upper() == 'EDITORIAL_SIGNAL':
        candidate=dict(selected)
        candidate['signal_first_primary']=False
        candidate['signal_first_editorial']=True
        candidate['type']=candidate.get('type') or 'editorial'
        candidate['selection_source']='signal_first_router'
        return candidate

    candidate=dict(selected)
    prediction=candidate.get('prediction') if isinstance(candidate.get('prediction'),dict) else {}
    setup=candidate.get('trade_setup') if isinstance(candidate.get('trade_setup'),dict) else {}
    for key,value in {
        'direction':prediction.get('direction') or setup.get('side'),
        'entry_trigger':prediction.get('entry_trigger') or setup.get('trigger'),
        'tp1':prediction.get('tp1') or setup.get('tp1'),
        'tp2':prediction.get('tp2') or setup.get('tp2'),
        'sl':prediction.get('sl') or setup.get('invalidation'),
        'confidence':prediction.get('confidence') or candidate.get('flow_confidence'),
    }.items():
        if value is not None: candidate[key]=value
    side=str(candidate.get('direction') or '').upper()
    try: conf=float(candidate.get('confidence') or 0)
    except Exception: conf=0
    complete=side in {'LONG','SHORT'} and all(candidate.get(k) is not None for k in ('entry_trigger','tp1','tp2','sl')) and conf>=65
    if not complete: return None
    candidate['signal_first_primary']=True
    candidate['type']='flow'
    candidate['lane']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
    candidate['category']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
    candidate['signal_router_version']=signal.get('router_version','')
    candidate['signal_thesis_key']=candidate.get('thesis_key','')
    return candidate

def candidate_pool(portfolio,pre,engagement,market,signal,stale_portfolio=False):
    pool,seen=[],set()
    selected_signal=signal_candidate(signal)
    if selected_signal: add_candidate(pool,seen,selected_signal,'signal_first_router')
    # Do not let a generic portfolio candidate outrank an authoritative router
    # selection. Portfolio recovery is only a fallback when the router found no
    # eligible story at all.
    if not selected_signal:
        for source,item in portfolio_candidates(portfolio): add_candidate(pool,seen,item,source)
    ranking=pre.get('opportunity_ranking_6') or {}
    selected_ranking=ranking.get('selected')
    if isinstance(selected_ranking,dict) and not selected_signal: add_candidate(pool,seen,selected_ranking,'opportunity_ranker_selected')
    if not selected_signal:
        for x in ranking.get('top_candidates') or []: add_candidate(pool,seen,x,'opportunity_ranker')
    if stale_portfolio and not selected_signal:
        for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
            for x in market.get(key) or []: add_candidate(pool,seen,x,f'market_candidate:{key}')
        return pool
    if selected_signal: return pool
    selected_pre=pre.get('selected_opportunity')
    if isinstance(selected_pre,dict): add_candidate(pool,seen,selected_pre,'preflight_selected_opportunity')
    for x in (engagement.get('selected'),)+tuple(engagement.get('ranked_candidates') or []):
        add_candidate(pool,seen,x,'engagement_candidate')
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(key) or []: add_candidate(pool,seen,x,f'market_candidate:{key}')
    return pool

def infer_category(candidate,source):
    existing=str(candidate.get('category') or candidate.get('lane') or '').strip().lower()
    allowed={'breaking_news','news_and_macro','top_gainers','top_losers','high_volatility','volume_leaders','new_listings','technical_setup','comparison','education','watchlist','research_insight','market_mechanism','data_surprise','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up','crypto_meme'}
    if existing in allowed: return existing
    if existing=='next_gainer_candidate': return 'top_gainers'
    if existing=='next_loser_candidate': return 'top_losers'
    if source.endswith(':top_gainers'): return 'top_gainers'
    if source.endswith(':top_losers'): return 'top_losers'
    if source.endswith(':highest_volume'): return 'volume_leaders'
    if source.endswith(':new_listing_market'): return 'new_listings'
    if source.endswith(':top_content_signals'): return 'technical_setup'
    if source in {'opportunity_ranker','opportunity_ranker_selected','signal_first_router'}: return 'technical_setup'
    if source.startswith('content_portfolio_guard'): return 'technical_setup'
    return 'technical_setup'

def prepare_candidate(candidate,source):
    item=dict(candidate); item['symbol']=symbol(item); item['category']=infer_category(item,source); item['lane']=str(item.get('lane') or item['category']); item['chart_symbols']=[base_symbol(item)]
    if not str(item.get('reason') or '').strip(): item['reason']=f'Fresh {item["category"].replace("_"," ")} market opportunity for {base_symbol(item)}; validate the move before acting.'
    if not str(item.get('instruction') or '').strip(): item['instruction']=f'Explain the evidence for {base_symbol(item)}, the confirmation condition, and the invalidation condition; do not present the setup as guaranteed.'
    return item

def main():
    pre=load(PRE); eng=load(ENGAGEMENT); market=load(MARKET); cadence=load(CADENCE); signal=load(SIGNAL); portfolio=load(PORTFOLIO)
    valid=trading_symbols()
    portfolio_selected=portfolio.get('selected') if isinstance(portfolio.get('selected'),dict) else {}
    portfolio_symbol=symbol(portfolio_selected); portfolio_exists=bool(portfolio.get('publish') and portfolio_symbol); stale_portfolio=bool(portfolio_exists and portfolio_symbol not in valid)
    if stale_portfolio: print(f'Portfolio selected stale/delisted asset: {portfolio_symbol}; entering NON-BTC research recovery')
    pool=candidate_pool(portfolio,pre,eng,market,signal,stale_portfolio=stale_portfolio)
    chosen=None; source=''
    signal_mode=bool(signal.get('publish') is True and signal_candidate(signal))
    for candidate in pool:
        s=symbol(candidate)
        if s not in valid:
            if s==portfolio_symbol: print(f'Skipping stale portfolio candidate: {s}')
            continue
        if stale_portfolio and base_symbol(candidate) in {'BTC','ETH'} and str(candidate.get('_freeze_source'))!='signal_first_router':
            print(f'Skipping reserve-asset recovery candidate: {base_symbol(candidate)}'); continue
        source_name=str(candidate.get('_freeze_source') or 'validated_candidate')
        prepared=prepare_candidate(candidate,source_name)
        # If the router selected an editorial story, preserve it. If it selected a
        # trade, only a complete trade contract may survive. Never substitute a
        # generic portfolio setup for either lane.
        if source_name=='signal_first_router' and bool(prepared.get('signal_first_editorial')):
            chosen=prepared; source=source_name; break
        if signal_mode and source_name!='signal_first_router':
            direction=str(prepared.get('direction') or '').upper()
            if direction not in {'LONG','SHORT'} or any(prepared.get(k) is None for k in ('entry_trigger','tp1','tp2','sl')):
                print(f'Rejecting non-prediction fallback during Signal-First cycle: {s}'); continue
        chosen=prepared; source=source_name; break
    if not chosen:
        raise SystemExit('NO_ELIGIBLE_OPPORTUNITY: no authoritative trade or editorial story survived validation')
    usdt=symbol(chosen)
    if usdt not in valid: raise SystemExit(f'Frozen opportunity is not a currently trading Binance symbol: {usdt}')
    sym=usdt[:-4]; chosen.pop('_freeze_source',None); chosen['symbol']=usdt
    chosen_score=min(100.0,max(0.0,max(score(chosen),score(cadence))))
    if chosen_score>0: chosen['selected_score']=chosen_score
    pre['selected_opportunity']=chosen
    director=pre.get('content_director_4')
    if not isinstance(director,dict): director={}
    primary=director.get('primary_story') if isinstance(director.get('primary_story'),dict) else {}
    primary.update({'symbol':sym,'category':chosen.get('category'),'lane':chosen.get('lane'),'chart_symbols':[sym],'reason':chosen.get('reason'),'instruction':chosen.get('instruction')}); director['primary_story']=primary; pre['content_director_4']=director
    news_authoritative=bool(chosen.get('news_title') and (chosen.get('news_override') or chosen.get('type')=='news' or chosen.get('category') in {'breaking_news','news_and_macro','news_market_impact'}))
    prediction=chosen.get('prediction') if isinstance(chosen.get('prediction'),dict) else {}
    trade_setup=chosen.get('trade_setup') if isinstance(chosen.get('trade_setup'),dict) else {}
    evidence=chosen.get('evidence') if isinstance(chosen.get('evidence'),dict) else {}
    frozen={'version':14,'frozen_at':datetime.now(timezone.utc).isoformat(),'symbol':sym,'symbol_usdt':usdt,'binance_verified':True,'category':chosen.get('category','technical_setup'),'lane':chosen.get('lane',chosen.get('category','technical_setup')),'reason':chosen.get('reason',''),'instruction':chosen.get('instruction',''),'score':chosen_score,'raw_score':min(100.0,max(0.0,score(chosen))),'adjusted_score':min(100.0,max(0.0,score(chosen))),'engagement_score':chosen.get('engagement_score',0),'selected_score':chosen_score,'effective_score':chosen_score,'run_ai':bool(pre.get('run_ai',False)),'selection_source':source,'portfolio_authoritative':source.startswith('content_portfolio_guard'),'signal_first_authoritative':source=='signal_first_router' and not bool(chosen.get('signal_first_editorial')),'signal_first_editorial':bool(chosen.get('signal_first_editorial')),'signal_router_version':chosen.get('signal_router_version',signal.get('router_version','')),'signal_thesis_key':chosen.get('signal_thesis_key',''),'direction':chosen.get('direction') or prediction.get('direction') or '','entry_trigger':chosen.get('entry_trigger') or prediction.get('entry_trigger'),'tp1':chosen.get('tp1') or prediction.get('tp1'),'tp2':chosen.get('tp2') or prediction.get('tp2'),'sl':chosen.get('sl') or prediction.get('sl'),'confidence':chosen.get('confidence') or prediction.get('confidence'),'conditional':bool(prediction.get('conditional',True)),'not_a_guarantee':bool(prediction.get('not_a_guarantee',True)),'trade_setup':trade_setup,'evidence':evidence,'stale_portfolio_recovered':stale_portfolio,'stale_portfolio_original_symbol':portfolio_symbol if stale_portfolio else '','news_authoritative':news_authoritative,'news_title':chosen.get('news_title',''),'news_source':chosen.get('news_source',chosen.get('source','')),'chart_symbols':[sym],'fallback_policy':'NEVER_FALLBACK_TO_BTC','recovery_policy':'STALE_PORTFOLIO_ONLY_NON_BTC_RESEARCHED_CANDIDATES'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(frozen,indent=2,ensure_ascii=False),encoding='utf-8'); PRE.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(frozen,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
