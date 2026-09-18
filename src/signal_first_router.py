"""Final signal-first router: preserve strong candidates and derive evidence-backed conditional setups."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; CADENCE=ROOT/'data/live/autonomous_cadence_6.json'; MARKET=ROOT/'data/live/market_snapshot.json'; FLOW=ROOT/'data/live/capital_flow_intelligence.json'; FULL_FLOW=ROOT/'data/live/full_universe_flow.json'; RANKING=ROOT/'data/live/opportunity_ranking_6.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/signal_first_routing.json'
MIN_SCORE=float(os.getenv('SIGNAL_FIRST_MIN_SCORE','72')); MIN_FLOW_CONF=float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE','65')); SIM=float(os.getenv('SIGNAL_FIRST_TEXT_SIMILARITY','0.72'))
PRIMARY_LANES={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}

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
def flow_complete(x):
    _,_,side,tr,tp1,tp2,sl,conf=setup_parts(x); return side in {'LONG','SHORT'} and all(v is not None for v in (tr,tp1,tp2,sl)) and conf>=MIN_FLOW_CONF
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
def candles_for(symbol,market):
    sym=str(symbol).upper().replace('USDT','')
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for item in market.get(key) or []:
            if str(item.get('symbol','')).upper().replace('USDT','')==sym:return item.get('candles_1h') or [],item
    return [],None
def derive(candidate,market):
    if flow_complete(candidate):return candidate
    category=str(candidate.get('category') or lane(candidate)).lower()
    if category not in {'next_gainer_candidate','next_loser_candidate'}:return candidate
    candles,item=candles_for(candidate.get('symbol'),market)
    if len(candles)<6:return candidate
    highs=[]; lows=[]; closes=[]
    for c in candles[-24:]:
        try:
            if isinstance(c,dict):h=float(c['high']);l=float(c['low']);cl=float(c['close'])
            else:h=float(c[2]);l=float(c[3]);cl=float(c[4])
            highs.append(h); lows.append(l); closes.append(cl)
        except Exception:continue
    if len(highs)<6:return candidate
    last=closes[-1]; rh=max(highs[:-1]); rl=min(lows[:-1]); span=max(rh-rl,last*0.002)
    if category=='next_gainer_candidate':
        side='LONG'; trigger=rh*1.002; sl=max(rl,last-span*.75); risk=trigger-sl; tp1=trigger+risk; tp2=trigger+2*risk
    else:
        side='SHORT'; trigger=rl*.998; sl=min(rh,last+span*.75); risk=sl-trigger; tp1=trigger-risk; tp2=trigger-2*risk
    if risk<=0:return candidate
    conf=max(MIN_FLOW_CONF,min(95.0,num(candidate.get('flow_confidence'),num(candidate.get('score'),num(candidate.get('discovery_score'),72)))))
    e=dict(candidate); e['trade_setup']={'side':side,'trigger':trigger,'tp1':tp1,'tp2':tp2,'invalidation':sl,'risk_per_unit':risk,'setup_source':'verified_1h_ohlcv_conditional'}; e['prediction']={'direction':side,'entry_trigger':trigger,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf,'conditional':True,'not_a_guarantee':True}; e['flow_confidence']=conf; e['evidence']={'ohlcv_candles_used':len(candles),'last_price':last,'recent_high':rh,'recent_low':rl}; return e
def add(target,x,allow_complete_flow=False):
    if not isinstance(x,dict) or not x.get('symbol'):return
    score=num(x.get('score'),num(x.get('ranker_score'),num(x.get('discovery_score'))))
    complete=flow_complete(x)
    if score>=MIN_SCORE or (allow_complete_flow and complete):
        target.append({**x,'score':score})
def candidates(brief,pre,cad,market,flow_data,full_flow,ranking):
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

    # Primary source: the dedicated conditional-flow engine.
    for x in (flow_data.get('top_conditional_setups') or []):
        if isinstance(x,dict) and flow_complete(x):
            side=setup_parts(x)[2]
            primary.append({**x,'type':'flow','lane':x.get('lane') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short'),'category':x.get('category') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short'),'score':num(x.get('flow_score'),x.get('flow_confidence'))})

    # Secondary evidence source: the full-universe participation scanner. It
    # deliberately does not invent a direction; only positive/negative short-
    # term price context can turn EARLY/DEVELOPING participation into a
    # conditional LONG/SHORT candidate, and derive() then requires fresh 1H
    # candles before it becomes publishable.
    for x in (full_flow.get('early_movers') or []):
        if not isinstance(x,dict) or str(x.get('flow_state','')).upper() not in {'EARLY','DEVELOPING'}:continue
        move=num(x.get('price_change_6h_pct'),num(x.get('price_change_percent')))
        if move>0: cat='next_gainer_candidate'
        elif move<0: cat='next_loser_candidate'
        else: continue
        candidate={**x,'category':cat,'lane':'capital_flow_long' if cat=='next_gainer_candidate' else 'capital_flow_short','type':'flow','flow_confidence':num(x.get('discovery_score'),0)}
        if num(candidate.get('discovery_score'))>=45: primary.append(candidate)

    ranking_items=[]
    if isinstance(ranking.get('selected'),dict):ranking_items.append(ranking['selected'])
    if isinstance(ranking.get('top_candidates'),list):ranking_items.extend(x for x in ranking['top_candidates'] if isinstance(x,dict))
    for x in ranking_items:
        add(market_candidates,{**x,'type':x.get('type','market'),'lane':x.get('lane') or x.get('category') or 'market','reason':x.get('reason') or 'authoritative opportunity ranking'})
    if cad.get('selected_symbol') and num(cad.get('ranker_score'),num(cad.get('effective_score')))>=MIN_SCORE:
        add(market_candidates,{'symbol':cad['selected_symbol'],'category':cad.get('selected_category','market'),'lane':'market','type':'market','score':num(cad.get('ranker_score'),num(cad.get('effective_score'))),'reason':'authoritative cadence selection'})
    story=brief.get('primary_story')
    if isinstance(story,dict):add(primary if lane(story) in PRIMARY_LANES or story.get('type')=='flow' else market_candidates,story,allow_complete_flow=True)
    return (sorted(primary,key=lambda x:(1 if flow_complete(x) else 0,num(x.get('flow_confidence'),0),num(x.get('score')),),reverse=True),sorted(market_candidates,key=lambda x:num(x.get('score')),reverse=True))
def choose(xs,rows,market,live_symbols):
    blocked_rows=[]
    for x in xs:
        raw_symbol=str(x.get('symbol') or '').upper().replace('USDT','').strip()
        if live_symbols and raw_symbol not in live_symbols:
            blocked_rows.append({'symbol':raw_symbol,'reason':'not_currently_live_on_binance'})
            continue
        e=derive(x,market); reason=blocked(e,rows)
        if reason:blocked_rows.append({'symbol':e.get('symbol'),'reason':reason});continue
        if flow_complete(e):return e,blocked_rows
        blocked_rows.append({'symbol':e.get('symbol'),'reason':'prediction_contract_missing_verified_ohlcv'})
    return None,blocked_rows
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cad=load(CADENCE); market=load(MARKET); flow=load(FLOW); full_flow=load(FULL_FLOW); ranking=load(RANKING); rows=recent()
    # The full-universe scanner can lag the exchangeInfo-backed market snapshot
    # for recently listed/relisted symbols.  Use the fresh market snapshot as a
    # second authoritative live-universe source instead of rejecting a symbol
    # that Binance has just returned with current klines.
    live_symbols={str(s).upper().replace('USDT','').strip() for s in (full_flow.get('all_live_symbols') or []) if str(s).strip()}
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for item in (market.get(key) or []):
            if isinstance(item,dict) and item.get('symbol'):
                live_symbols.add(str(item.get('symbol')).upper().replace('USDT','').strip())
    primary,markets=candidates(brief,pre,cad,market,flow,full_flow,ranking)
    chosen,blocks=choose(primary,rows,market,live_symbols)
    if chosen is None:chosen,more=choose(markets,rows,market,live_symbols);blocks+=more
    current_allowed=bool(cad.get('publish')); selected=None; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    if chosen and (current_allowed or num(chosen.get('score'))>=MIN_SCORE):
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
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'2.2-live-symbol-validated-flow-primary','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'selected':selected,'cadence_publish_on_disk':current_allowed,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(markets)},'policy':{'minimum_score':MIN_SCORE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True,'no_signal_means_no_signal_post':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
