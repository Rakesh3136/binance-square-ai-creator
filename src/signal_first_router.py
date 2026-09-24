"""Final signal-first router: preserve strong candidates and derive evidence-backed conditional setups."""
from __future__ import annotations
import json, os, re, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; CADENCE=ROOT/'data/live/autonomous_cadence_6.json'; MARKET=ROOT/'data/live/market_snapshot.json'; FLOW=ROOT/'data/live/capital_flow_intelligence.json'; FULL_FLOW=ROOT/'data/live/full_universe_flow.json'; RANKING=ROOT/'data/live/opportunity_ranking_6.json'; PRE_ROUTER=ROOT/'data/live/pre_router_intelligence.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/signal_first_routing.json'
MIN_SCORE=float(os.getenv('SIGNAL_FIRST_MIN_SCORE','72')); MIN_FLOW_CONF=float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE','65')); SIM=float(os.getenv('SIGNAL_FIRST_TEXT_SIMILARITY','0.72'))
PRIMARY_LANES={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}
EDITORIAL_LANES={'breaking_news','news_and_macro','top_gainers','top_losers','high_volatility','volume_leaders','new_listings','comparison','education','watchlist','crypto_meme'}

def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
def num(v,d=0.0):
    try:return float(v)
    except Exception:return d
def lane(x):return str(x.get('lane') or x.get('type') or x.get('category') or '').lower()
def text(x):return x.get('post') or x.get('text') or x.get('content') or x.get('draft') or x.get('body') or ''
def recent():
    if not PUBLICATIONS.exists():return []
    good={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_SUBMITTED_504'}; out=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-120:]:
        try:
            r=json.loads(line)
            if isinstance(r,dict) and r.get('status') in good:out.append(r)
        except Exception:pass
    return out[-20:]
def setup_parts(x):
    s=x.get('trade_setup') if isinstance(x.get('trade_setup'),dict) else {}; p=x.get('prediction') if isinstance(x.get('prediction'),dict) else {}
    side=str(s.get('side') or p.get('direction') or x.get('flow_side') or '').upper(); tr=s.get('trigger',p.get('entry_trigger')); tp1=s.get('tp1',p.get('tp1')); tp2=s.get('tp2',p.get('tp2')); sl=s.get('invalidation',p.get('sl')); conf=num(x.get('flow_confidence'),num((x.get('multitimeframe') or {}).get('confidence'),num(p.get('confidence'),num(x.get('score')))))
    return s,p,side,tr,tp1,tp2,sl,conf
def level_contract_valid(side,tr,tp1,tp2,sl):
    try:
        e,a,b,stop=[float(v) for v in (tr,tp1,tp2,sl)]
    except (TypeError,ValueError):
        return False
    if min(e,a,b,stop) <= 0:
        return False
    if side == 'LONG':
        return stop < e < a <= b
    if side == 'SHORT':
        return 0 < b <= a < e < stop
    return False


def editorial_complete(x):
    """Validate a non-trading editorial opportunity without manufacturing a trade setup."""
    category=str(x.get('category') or lane(x)).lower()
    if category not in EDITORIAL_LANES: return False
    score=num(x.get('score'),num(x.get('ranker_score'),num(x.get('news_score'))))
    if score < MIN_SCORE: return False
    symbol=str(x.get('symbol') or '').upper().replace('USDT','').strip()
    if not symbol: return False
    if category in {'breaking_news','news_and_macro'}:
        if not str(x.get('title') or x.get('news_title') or '').strip(): return False
        if not str(x.get('source') or x.get('news_source') or '').strip(): return False
        if not str(x.get('published_at') or x.get('news_published_at') or '').strip(): return False
    if category=='crypto_meme':
        if not str(x.get('meme_context') or x.get('reason') or '').strip(): return False
        if str(x.get('meme_source_type') or '').strip() not in {'market_move','news','existing_evidence'}: return False
    return True

def flow_complete(x):
    _,_,side,tr,tp1,tp2,sl,conf=setup_parts(x)
    return side in {'LONG','SHORT'} and level_contract_valid(side,tr,tp1,tp2,sl) and conf>=MIN_FLOW_CONF
def norm(v):
    v=re.sub(r'\$?[0-9]+(?:\.[0-9]+)?',' ',str(v or '').lower()); return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]+',' ',v)).strip()
def blocked(x,rows):
    sym=str(x.get('symbol') or '').upper(); _,_,side,_,_,_,_,_=setup_parts(x)
    for r in rows[-5:]:
        rs=str(r.get('symbol') or '').upper(); rside=str(r.get('direction') or r.get('side') or r.get('flow_side') or '').upper()
        if sym and rs==sym and side and rside==side:return 'same_symbol_and_direction_recent'
        old=norm(text(r)); new=norm(text(x))
        if new and old and SequenceMatcher(None,new,old).ratio()>=SIM:return 'high_text_similarity_recent'
    return ''
def trading_symbols():
    """Return Binance's current TRADING spot symbols; never infer tradability from market snapshots."""
    bases=('https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com')
    last=None
    for api in bases:
        try:
            req=urllib.request.Request(api+'/api/v3/exchangeInfo?symbolStatus=TRADING',headers={'User-Agent':'binance-square-ai-creator/4.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as h:
                data=json.loads(h.read().decode('utf-8'))
            symbols={str(x.get('symbol','')).upper() for x in data.get('symbols',[]) if str(x.get('status','')).upper()=='TRADING'}
            if symbols:return {s[:-4] if s.endswith('USDT') else s for s in symbols if s.endswith('USDT')}
        except Exception as exc:last=exc
    raise RuntimeError(f'Unable to verify Binance trading symbols before Signal-First selection: {last}')
BINANCE_BASES=(
    'https://data-api.binance.vision',
    'https://api-gcp.binance.com',
    'https://api1.binance.com',
    'https://api2.binance.com',
)

def candles_for(symbol,market):
    sym=str(symbol).upper().replace('USDT','')
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for item in market.get(key) or []:
            if str(item.get('symbol','')).upper().replace('USDT','')==sym:
                return item.get('candles_1h') or [],item
    return [],None

def fetch_verified_1h_candles(symbol, limit=48):
    """Fetch fresh completed Binance Spot 1H candles for the selected live symbol."""
    clean=str(symbol or '').upper().replace('BINANCE:','').replace('USDT','').strip()
    if not clean:
        return []
    request_symbol=f'{clean}USDT'
    now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
    last=None
    for base in BINANCE_BASES:
        try:
            url=base+'/api/v3/klines?'+urllib.parse.urlencode({
                'symbol':request_symbol,
                'interval':'1h',
                'limit':str(limit),
            })
            req=urllib.request.Request(
                url,
                headers={'User-Agent':'binance-square-ai-creator/4.0','Accept':'application/json'},
            )
            with urllib.request.urlopen(req,timeout=20) as h:
                raw=json.loads(h.read().decode('utf-8'))
            candles=[]
            for row in raw:
                try:
                    close_time=int(row[6])
                    if close_time>=now_ms:
                        continue
                    candles.append({
                        'open_time':int(row[0]),
                        'open':float(row[1]),
                        'high':float(row[2]),
                        'low':float(row[3]),
                        'close':float(row[4]),
                        'volume':float(row[5]),
                        'close_time':close_time,
                    })
                except (TypeError,ValueError,IndexError):
                    continue
            if len(candles)>=20:
                return candles
            last=RuntimeError(f'only {len(candles)} completed 1H candles returned for {clean}')
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
            last=exc
    raise RuntimeError(f'Unable to fetch verified completed 1H OHLCV for {clean}: {last}')

def derive(candidate,market):
    if flow_complete(candidate):
        evidence=candidate.get('evidence') if isinstance(candidate.get('evidence'),dict) else {}
        if num(evidence.get('ohlcv_candles_used'))>=20 and str(evidence.get('provenance','')).startswith('binance_spot_'):
            return candidate

    candles,item=candles_for(candidate.get('symbol'),market)
    if len(candles)<20:
        candles=fetch_verified_1h_candles(candidate.get('symbol'),limit=48)
    else:
        # The scanner snapshot may contain an open candle; use only completed
        # candles and refresh when fewer than 20 completed candles remain.
        now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
        completed=[]
        for c in candles:
            try:
                close_time=int(c.get('close_time',0)) if isinstance(c,dict) else 0
                if close_time<=0 or close_time<now_ms:
                    completed.append(c)
            except Exception:
                continue
        candles=completed
        if len(candles)<20:
            candles=fetch_verified_1h_candles(candidate.get('symbol'),limit=48)

    if len(candles)<20:
        return candidate

    highs=[]; lows=[]; closes=[]
    for c in candles[-24:]:
        try:
            if isinstance(c,dict):
                h=float(c['high']); l=float(c['low']); cl=float(c['close'])
            else:
                h=float(c[2]); l=float(c[3]); cl=float(c[4])
            highs.append(h); lows.append(l); closes.append(cl)
        except Exception:
            continue
    if len(highs)<20:
        return candidate

    # Preserve the upstream direction when present; otherwise infer only from
    # the candidate's observed signed move. Never fabricate a directional signal.
    _,existing_prediction,existing_side,_,_,_,_,existing_conf=setup_parts(candidate)
    category=str(candidate.get('category') or lane(candidate)).lower()
    side=existing_side if existing_side in {'LONG','SHORT'} else (
        'LONG' if num(candidate.get('price_change_6h_pct'),num(candidate.get('price_change_percent')))>=0
        else 'SHORT'
    )
    last=closes[-1]
    rh=max(highs[:-1]); rl=min(lows[:-1]); span=max(rh-rl,last*0.002)
    if last<=0 or rh<=0 or rl<=0:
        return candidate
    if side=='LONG':
        trigger=max(last,rh)*1.002
        sl=min(rl,last-span*0.75)
        risk=trigger-sl
        if risk<=0:return candidate
        tp1=trigger+risk; tp2=trigger+2*risk
    else:
        trigger=min(last,rl)*0.998
        sl=max(rh,last+span*0.75)
        risk=sl-trigger
        risk=min(risk,trigger*0.45)
        if risk<=0:return candidate
        tp1=trigger-risk; tp2=trigger-2*risk

    if not level_contract_valid(side,trigger,tp1,tp2,sl):
        return candidate

    conf=max(
        MIN_FLOW_CONF,
        min(95.0,num(candidate.get('flow_confidence'),num(candidate.get('score'),num(candidate.get('discovery_score'),existing_conf or 72))))
    )
    e=dict(candidate)
    e['trade_setup']={
        'side':side,
        'trigger':trigger,
        'tp1':tp1,
        'tp2':tp2,
        'invalidation':sl,
        'risk_per_unit':risk,
        'setup_source':'verified_completed_binance_1h_ohlcv_conditional',
    }
    e['prediction']={
        'direction':side,
        'entry_trigger':trigger,
        'tp1':tp1,
        'tp2':tp2,
        'sl':sl,
        'confidence':conf,
        'conditional':True,
        'not_a_guarantee':True,
    }
    e['flow_confidence']=max(num(candidate.get('flow_confidence')),conf)
    e['evidence']={
        'provenance':'binance_spot_1h_klines_completed_candles',
        'ohlcv_candles_used':len(candles),
        'last_price':last,
        'recent_high':rh,
        'recent_low':rl,
        'data_cutoff':candles[-1].get('close_time') if isinstance(candles[-1],dict) else None,
        'candles_1h':candles[-24:],
    }
    e['signal_first_ohlcv_verified']=True
    e['prediction_contract_complete']=True
    return e
def add(target,x,allow_complete_flow=False):
    if not isinstance(x,dict) or not x.get('symbol'):return
    score=num(x.get('score'),num(x.get('ranker_score'),num(x.get('discovery_score'))))
    complete=flow_complete(x)
    if score>=MIN_SCORE or (allow_complete_flow and complete):
        target.append({**x,'score':score})
def candidates(brief,pre,cad,market,flow_data,full_flow,ranking,pre_router):
    primary=[]; market_candidates=[]
    for source in (brief.get('ranked_stories'),pre.get('ranked_stories')):
        if isinstance(source,list):
            for x in source:
                if not isinstance(x,dict) or not x.get('symbol'):continue
                score=num(x.get('score'),num(x.get('ranker_score'),num(x.get('discovery_score'))))
                is_flow=lane(x) in PRIMARY_LANES or x.get('type')=='flow'
                if is_flow and (score>=MIN_SCORE or flow_complete(x)):
                    primary.append({**x,'score':score})
                elif score>=MIN_SCORE:
                    market_candidates.append({**x,'score':score})
    selected=pre.get('selected_opportunity')
    if isinstance(selected,dict):
        selected_is_flow=lane(selected) in PRIMARY_LANES or selected.get('type')=='flow' or flow_complete(selected)
        add(primary if selected_is_flow else market_candidates,selected,allow_complete_flow=selected_is_flow)

    for x in (flow_data.get('top_conditional_setups') or []):
        if isinstance(x,dict) and flow_complete(x):
            side=setup_parts(x)[2]
            primary.append({**x,'type':'flow','lane':x.get('lane') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short'),'category':x.get('category') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short'),'score':num(x.get('flow_score'),x.get('flow_confidence'))})

    for x in (full_flow.get('early_movers') or []):
        if not isinstance(x,dict) or str(x.get('flow_state','')).upper() not in {'EARLY','DEVELOPING'}:continue
        move=num(x.get('price_change_6h_pct'),num(x.get('price_change_percent')))
        if move>0: cat='next_gainer_candidate'
        elif move<0: cat='next_loser_candidate'
        else: continue
        candidate={**x,'category':cat,'lane':'capital_flow_long' if cat=='next_gainer_candidate' else 'capital_flow_short','type':'flow','flow_confidence':num(x.get('discovery_score'),0)}
        if num(candidate.get('discovery_score'))>=45: primary.append(candidate)

    for x in (market.get('top_content_signals') or []):
        if not isinstance(x,dict) or not x.get('symbol'): continue
        move=num(x.get('price_change_6h_pct'),num(x.get('price_change_percent')))
        if move == 0: continue
        cat='next_gainer_candidate' if move > 0 else 'next_loser_candidate'
        candidate={**x,'category':cat,'lane':'capital_flow_long' if move > 0 else 'capital_flow_short','type':'flow','flow_confidence':num(x.get('content_signal_score'),num(x.get('score'),72))}
        if num(candidate.get('content_signal_score'),0) >= MIN_SCORE:
            primary.append(candidate)

    ranking_items=[]
    if isinstance(ranking.get('selected'),dict):ranking_items.append(ranking['selected'])
    if isinstance(ranking.get('top_candidates'),list):ranking_items.extend(x for x in ranking['top_candidates'] if isinstance(x,dict))
    for x in ranking_items:
        add(market_candidates,{**x,'type':x.get('type','market'),'lane':x.get('lane') or x.get('category') or 'market','reason':x.get('reason') or 'authoritative opportunity ranking'})
    if cad.get('selected_symbol') and num(cad.get('ranker_score'),num(cad.get('effective_score')))>=MIN_SCORE:
        add(market_candidates,{'symbol':cad['selected_symbol'],'category':cad.get('selected_category','market'),'lane':'market','type':'market','score':num(cad.get('ranker_score'),num(cad.get('effective_score'))),'reason':'authoritative cadence selection'})
    # Discovery shortlist from the pre-router intelligence layer. This never grants
    # publication authority; choose() still re-verifies live status, OHLCV and contract.
    for x in (pre_router.get('shortlist') or [])[:40]:
        if isinstance(x,dict) and x.get('symbol'):
            add(primary, {**x, 'type':'flow', 'lane':x.get('lane') or 'flow', 'category':x.get('category') or 'flow', 'score':num(x.get('pre_router_priority'))})

    story=brief.get('primary_story')
    if isinstance(story,dict):add(primary if lane(story) in PRIMARY_LANES or story.get('type')=='flow' else market_candidates,story,allow_complete_flow=True)
    return (sorted(primary,key=lambda x:(1 if flow_complete(x) else 0,num(x.get('flow_confidence'),0),num(x.get('score')),),reverse=True),sorted(market_candidates,key=lambda x:num(x.get('score')),reverse=True))
def choose(xs,rows,market,live_symbols,allow_editorial=False):
    blocked_rows=[]
    for x in xs:
        raw_symbol=str(x.get('symbol') or '').upper().replace('USDT','').strip()
        if raw_symbol not in live_symbols:
            blocked_rows.append({'symbol':raw_symbol,'reason':'not_currently_live_on_binance'}); continue
        category=str(x.get('category') or lane(x)).lower()
        if category in EDITORIAL_LANES and allow_editorial and editorial_complete(x):
            e=dict(x)
            e['type']=e.get('type') or 'editorial'
            e['editorial_only']=True
            e['signal_first_primary']=False
            if category in {'breaking_news','news_and_macro'}:
                e['news_title']=e.get('news_title') or e.get('title') or ''
                e['news_source']=e.get('news_source') or e.get('source') or ''
                e['news_published_at']=e.get('news_published_at') or e.get('published_at') or ''
                s=str(e.get('symbol') or '').upper().replace('USDT','').replace('
        try: e=derive(x,market)
        except Exception as exc:
            blocked_rows.append({'symbol':raw_symbol,'reason':f'verified_ohlcv_fetch_failed:{type(exc).__name__}'}); continue
        reason=blocked(e,rows)
        if reason:
            blocked_rows.append({'symbol':e.get('symbol'),'reason':reason}); continue
        if flow_complete(e): return e,blocked_rows
        blocked_rows.append({'symbol':e.get('symbol'),'reason':'prediction_contract_missing_verified_ohlcv'})
    return None,blocked_rows
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cad=load(CADENCE); market=load(MARKET); flow=load(FLOW); full_flow=load(FULL_FLOW); ranking=load(RANKING); pre_router=load(PRE_ROUTER); macro=load(ROOT/'data/live/global_macro_intelligence.json'); rows=recent()
    # ExchangeInfo is authoritative; scanner snapshots are evidence only.
    live_symbols=trading_symbols()
    primary,markets=candidates(brief,pre,cad,market,flow,full_flow,ranking,pre_router)
    for event in (macro.get('events') or [])[:30]:
        title=str(event.get('title') or '').strip(); source=str(event.get('source') or '').strip(); published=str(event.get('published_at') or '').strip(); themes=event.get('themes') if isinstance(event.get('themes'),list) else []
        score=min(100,64 + len(themes)*5 + (4 if event.get('primary_theme') in {'geopolitical_risk','monetary_policy','inflation','energy_shock'} else 0))
        for raw in (event.get('asset_symbols') or [])[:2]:
            s=str(raw).upper().replace('    # Remove stale snapshot/ranker symbols before they reach authoritative selection.
    # choose() still performs the final live-universe check as a defense in depth.
    primary=[x for x in primary if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    markets=[x for x in markets if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    chosen,blocks=choose(primary,rows,market,live_symbols,allow_editorial=True)
    if chosen is None:chosen,more=choose(markets,rows,market,live_symbols,allow_editorial=True);blocks+=more
    current_allowed=bool(cad.get('publish')); selected=None; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    # Cadence is a pacing preference, not an authority gate. choose() already
    # requires a live Binance symbol, non-repetitive candidate, and a complete
    # verified 1H OHLCV trade contract. Never discard that evidence-backed setup
    # merely because the adaptive cadence scorer returned publish=false.
    cadence_override=bool(chosen and not current_allowed)
    if chosen:
        primary_signal=flow_complete(chosen) or lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if primary_signal:
            side=setup_parts(chosen)[2]
            chosen['type']='flow'
            chosen['lane']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
            chosen['category']=chosen.get('category') if chosen.get('category') in PRIMARY_LANES else ('capital_flow_long' if side=='LONG' else 'capital_flow_short')
        decision='PRIMARY_SIGNAL' if primary_signal else 'MARKET_SIGNAL'
        reason='qualified_conditional_signal_selected'
        selected=dict(chosen)
    if selected:
        _,pred,side,tr,tp1,tp2,sl,conf=setup_parts(selected); selected['signal_first_primary']=primary_signal; selected['prediction_contract_complete']=bool(flow_complete(selected)); selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':True,'prediction':pred}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'2.5-contract-surface-consistent','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'selected':selected,'prediction_contract_complete':bool(selected and selected.get('prediction_contract_complete') is True),'cadence_publish_on_disk':current_allowed,'cadence_override':cadence_override,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(markets),'live_usdt_symbols':len(live_symbols),'pre_router_shortlist':len(pre_router.get('shortlist') or [])},'verified_ohlcv_policy':{'minimum_completed_1h_candles':20,'refresh_limit':48,'source':'Binance Spot /api/v3/klines','reject_open_candle':True},'live_symbol_source':'binance_exchangeInfo_TRADING','pre_router_intelligence':{'used':bool(pre_router),'discovery_only':True},'policy':{'minimum_score':MIN_SCORE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True,'no_signal_means_no_trade_setup_post':True,'editorial_lanes_may_publish_without_trade_contract':True,'cadence_is_pacing_not_evidence_gate':True,'contract_flag_mirrors_selected_contract':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
,'').replace('USDT','').strip()
            if s and title and source and published:
                markets.append({'type':'news','category':'news_and_macro','lane':'news_and_macro','symbol':s,'score':score,'title':title,'source':source,'published_at':published,'reason':'verified macro event explicitly anchored to this asset','content_intent':'event_to_cross_asset_crypto_impact'})
    # Remove stale snapshot/ranker symbols before they reach authoritative selection.
    # choose() still performs the final live-universe check as a defense in depth.
    primary=[x for x in primary if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    markets=[x for x in markets if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    chosen,blocks=choose(primary,rows,market,live_symbols)
    if chosen is None:chosen,more=choose(markets,rows,market,live_symbols);blocks+=more
    current_allowed=bool(cad.get('publish')); selected=None; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    # Cadence is a pacing preference, not an authority gate. choose() already
    # requires a live Binance symbol, non-repetitive candidate, and a complete
    # verified 1H OHLCV trade contract. Never discard that evidence-backed setup
    # merely because the adaptive cadence scorer returned publish=false.
    cadence_override=bool(chosen and not current_allowed)
    if chosen:
        primary_signal=flow_complete(chosen) or lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if primary_signal:
            side=setup_parts(chosen)[2]
            chosen['type']='flow'
            chosen['lane']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
            chosen['category']=chosen.get('category') if chosen.get('category') in PRIMARY_LANES else ('capital_flow_long' if side=='LONG' else 'capital_flow_short')
        decision='PRIMARY_SIGNAL' if primary_signal else 'MARKET_SIGNAL'
        reason='qualified_conditional_signal_selected'
        selected=dict(chosen)
    if selected:
        _,pred,side,tr,tp1,tp2,sl,conf=setup_parts(selected); selected['signal_first_primary']=primary_signal; selected['prediction_contract_complete']=True; selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':True,'prediction':pred}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'2.5-contract-surface-consistent','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'selected':selected,'prediction_contract_complete':bool(selected and selected.get('prediction_contract_complete') is True),'cadence_publish_on_disk':current_allowed,'cadence_override':cadence_override,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(markets),'live_usdt_symbols':len(live_symbols),'pre_router_shortlist':len(pre_router.get('shortlist') or [])},'verified_ohlcv_policy':{'minimum_completed_1h_candles':20,'refresh_limit':48,'source':'Binance Spot /api/v3/klines','reject_open_candle':True},'live_symbol_source':'binance_exchangeInfo_TRADING','pre_router_intelligence':{'used':bool(pre_router),'discovery_only':True},'policy':{'minimum_score':MIN_SCORE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True,'no_signal_means_no_signal_post':True,'cadence_is_pacing_not_evidence_gate':True,'contract_flag_mirrors_selected_contract':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
,'').strip()
                e['news_symbols']=list(dict.fromkeys([*(e.get('news_symbols') or []), s])) if s else list(e.get('news_symbols') or [])
            return e,blocked_rows
        try: e=derive(x,market)
        except Exception as exc:
            blocked_rows.append({'symbol':raw_symbol,'reason':f'verified_ohlcv_fetch_failed:{type(exc).__name__}'}); continue
        reason=blocked(e,rows)
        if reason:
            blocked_rows.append({'symbol':e.get('symbol'),'reason':reason}); continue
        if flow_complete(e): return e,blocked_rows
        blocked_rows.append({'symbol':e.get('symbol'),'reason':'prediction_contract_missing_verified_ohlcv'})
    return None,blocked_rows
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cad=load(CADENCE); market=load(MARKET); flow=load(FLOW); full_flow=load(FULL_FLOW); ranking=load(RANKING); pre_router=load(PRE_ROUTER); macro=load(ROOT/'data/live/global_macro_intelligence.json'); rows=recent()
    # ExchangeInfo is authoritative; scanner snapshots are evidence only.
    live_symbols=trading_symbols()
    primary,markets=candidates(brief,pre,cad,market,flow,full_flow,ranking,pre_router)
    for event in (macro.get('events') or [])[:30]:
        title=str(event.get('title') or '').strip(); source=str(event.get('source') or '').strip(); published=str(event.get('published_at') or '').strip(); themes=event.get('themes') if isinstance(event.get('themes'),list) else []
        score=min(100,64 + len(themes)*5 + (4 if event.get('primary_theme') in {'geopolitical_risk','monetary_policy','inflation','energy_shock'} else 0))
        for raw in (event.get('asset_symbols') or [])[:2]:
            s=str(raw).upper().replace('    # Remove stale snapshot/ranker symbols before they reach authoritative selection.
    # choose() still performs the final live-universe check as a defense in depth.
    primary=[x for x in primary if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    markets=[x for x in markets if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    chosen,blocks=choose(primary,rows,market,live_symbols,allow_editorial=True)
    if chosen is None:chosen,more=choose(markets,rows,market,live_symbols,allow_editorial=True);blocks+=more
    current_allowed=bool(cad.get('publish')); selected=None; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    # Cadence is a pacing preference, not an authority gate. choose() already
    # requires a live Binance symbol, non-repetitive candidate, and a complete
    # verified 1H OHLCV trade contract. Never discard that evidence-backed setup
    # merely because the adaptive cadence scorer returned publish=false.
    cadence_override=bool(chosen and not current_allowed)
    if chosen:
        primary_signal=flow_complete(chosen) or lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if primary_signal:
            side=setup_parts(chosen)[2]
            chosen['type']='flow'
            chosen['lane']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
            chosen['category']=chosen.get('category') if chosen.get('category') in PRIMARY_LANES else ('capital_flow_long' if side=='LONG' else 'capital_flow_short')
        decision='PRIMARY_SIGNAL' if primary_signal else 'MARKET_SIGNAL'
        reason='qualified_conditional_signal_selected'
        selected=dict(chosen)
    if selected:
        _,pred,side,tr,tp1,tp2,sl,conf=setup_parts(selected); selected['signal_first_primary']=primary_signal; selected['prediction_contract_complete']=bool(flow_complete(selected)); selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':True,'prediction':pred}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'2.5-contract-surface-consistent','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'selected':selected,'prediction_contract_complete':bool(selected and selected.get('prediction_contract_complete') is True),'cadence_publish_on_disk':current_allowed,'cadence_override':cadence_override,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(markets),'live_usdt_symbols':len(live_symbols),'pre_router_shortlist':len(pre_router.get('shortlist') or [])},'verified_ohlcv_policy':{'minimum_completed_1h_candles':20,'refresh_limit':48,'source':'Binance Spot /api/v3/klines','reject_open_candle':True},'live_symbol_source':'binance_exchangeInfo_TRADING','pre_router_intelligence':{'used':bool(pre_router),'discovery_only':True},'policy':{'minimum_score':MIN_SCORE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True,'no_signal_means_no_trade_setup_post':True,'editorial_lanes_may_publish_without_trade_contract':True,'cadence_is_pacing_not_evidence_gate':True,'contract_flag_mirrors_selected_contract':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
,'').replace('USDT','').strip()
            if s and title and source and published:
                markets.append({'type':'news','category':'news_and_macro','lane':'news_and_macro','symbol':s,'score':score,'title':title,'source':source,'published_at':published,'reason':'verified macro event explicitly anchored to this asset','content_intent':'event_to_cross_asset_crypto_impact'})
    # Remove stale snapshot/ranker symbols before they reach authoritative selection.
    # choose() still performs the final live-universe check as a defense in depth.
    primary=[x for x in primary if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    markets=[x for x in markets if str(x.get('symbol') or '').upper().replace('USDT','').strip() in live_symbols]
    chosen,blocks=choose(primary,rows,market,live_symbols)
    if chosen is None:chosen,more=choose(markets,rows,market,live_symbols);blocks+=more
    current_allowed=bool(cad.get('publish')); selected=None; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    # Cadence is a pacing preference, not an authority gate. choose() already
    # requires a live Binance symbol, non-repetitive candidate, and a complete
    # verified 1H OHLCV trade contract. Never discard that evidence-backed setup
    # merely because the adaptive cadence scorer returned publish=false.
    cadence_override=bool(chosen and not current_allowed)
    if chosen:
        primary_signal=flow_complete(chosen) or lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if primary_signal:
            side=setup_parts(chosen)[2]
            chosen['type']='flow'
            chosen['lane']='capital_flow_long' if side=='LONG' else 'capital_flow_short'
            chosen['category']=chosen.get('category') if chosen.get('category') in PRIMARY_LANES else ('capital_flow_long' if side=='LONG' else 'capital_flow_short')
        decision='PRIMARY_SIGNAL' if primary_signal else 'MARKET_SIGNAL'
        reason='qualified_conditional_signal_selected'
        selected=dict(chosen)
    if selected:
        _,pred,side,tr,tp1,tp2,sl,conf=setup_parts(selected); selected['signal_first_primary']=primary_signal; selected['prediction_contract_complete']=True; selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':True,'prediction':pred}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'2.5-contract-surface-consistent','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'selected':selected,'prediction_contract_complete':bool(selected and selected.get('prediction_contract_complete') is True),'cadence_publish_on_disk':current_allowed,'cadence_override':cadence_override,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(markets),'live_usdt_symbols':len(live_symbols),'pre_router_shortlist':len(pre_router.get('shortlist') or [])},'verified_ohlcv_policy':{'minimum_completed_1h_candles':20,'refresh_limit':48,'source':'Binance Spot /api/v3/klines','reject_open_candle':True},'live_symbol_source':'binance_exchangeInfo_TRADING','pre_router_intelligence':{'used':bool(pre_router),'discovery_only':True},'policy':{'minimum_score':MIN_SCORE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True,'no_signal_means_no_signal_post':True,'cadence_is_pacing_not_evidence_gate':True,'contract_flag_mirrors_selected_contract':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
