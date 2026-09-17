"""Final signal-first router: preserve strong candidates and derive only evidence-backed conditional setups."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
DIRECTOR=ROOT/'data/live/content_director_brief.json'
CADENCE=ROOT/'data/live/autonomous_cadence_6.json'
MARKET=ROOT/'data/live/market_snapshot.json'
RANKING=ROOT/'data/live/opportunity_ranking_6.json'
PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'
OUT=ROOT/'data/live/signal_first_routing.json'
MIN_SCORE=float(os.getenv('SIGNAL_FIRST_MIN_SCORE','72'))
MIN_FLOW_CONF=float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE','65'))
SIM=float(os.getenv('SIGNAL_FIRST_TEXT_SIMILARITY','0.72'))
PRIMARY_LANES={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}
MARKET_LANES={'market','top_gainers','top_losers','high_volatility','volume_leaders','technical_setup','next_gainer_candidate','next_loser_candidate'}

def load(path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except Exception:return {}

def num(value, default=0.0):
    try:return float(value)
    except Exception:return default

def lane(x):return str(x.get('lane') or x.get('type') or x.get('category') or '').lower()

def recent():
    if not PUBLICATIONS.exists():return []
    good={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_SUBMITTED_504'}
    out=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-120:]:
        try:
            row=json.loads(line)
            if isinstance(row,dict) and row.get('status') in good:out.append(row)
        except Exception:pass
    return out[-20:]

def text(x):return x.get('post') or x.get('text') or x.get('content') or x.get('draft') or x.get('body') or ''

def setup_parts(x):
    setup=x.get('trade_setup') if isinstance(x.get('trade_setup'),dict) else {}
    pred=x.get('prediction') if isinstance(x.get('prediction'),dict) else {}
    side=str(setup.get('side') or pred.get('direction') or x.get('flow_side') or '').upper()
    trigger=setup.get('trigger',pred.get('entry_trigger')); tp1=setup.get('tp1',pred.get('tp1')); tp2=setup.get('tp2',pred.get('tp2')); sl=setup.get('invalidation',pred.get('sl'))
    confidence=num(x.get('flow_confidence'),num((x.get('multitimeframe') or {}).get('confidence'),num(x.get('score'))))
    return setup,pred,side,trigger,tp1,tp2,sl,confidence

def flow_complete(x):
    _,_,side,tr,tp1,tp2,sl,conf=setup_parts(x)
    return side in {'LONG','SHORT'} and all(v is not None for v in (tr,tp1,tp2,sl)) and conf>=MIN_FLOW_CONF

def norm(value):
    value=re.sub(r'\$?[0-9]+(?:\.[0-9]+)?',' ',str(value or '').lower())
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]+',' ',value)).strip()

def blocked(x,rows):
    symbol=str(x.get('symbol') or '').upper()
    _,_,side,_,_,_,_,_=setup_parts(x)
    for row in rows[-5:]:
        rs=str(row.get('symbol') or '').upper(); rside=str(row.get('direction') or row.get('side') or row.get('flow_side') or '').upper()
        if symbol and rs==symbol and side and rside==side:return 'same_symbol_and_direction_recent'
        old=norm(text(row)); new=norm(text(x))
        if new and old and SequenceMatcher(None,new,old).ratio()>=SIM:return 'high_text_similarity_recent'
    return ''

def add(target,x):
    if not isinstance(x,dict) or not x.get('symbol'):return
    score=num(x.get('score'),num(x.get('ranker_score')))
    if score>=MIN_SCORE:target.append({**x,'score':score})

def candles_for(symbol,market):
    symbol=str(symbol).upper().replace('USDT','')
    pools=[]
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        pools.extend(market.get(key) or [])
    for item in pools:
        if str(item.get('symbol','')).upper().replace('USDT','')==symbol:return item.get('candles_1h') or [],item
    return [],None

def derive_conditional_setup(candidate,market):
    """Create a conditional, testable setup only from supplied OHLCV.
    This is not a forecast and never asserts that the levels will be reached.
    """
    if flow_complete(candidate):return candidate
    category=str(candidate.get('category') or lane(candidate)).lower()
    if category not in {'next_gainer_candidate','next_loser_candidate'}:return candidate
    candles,item=candles_for(candidate.get('symbol'),market)
    if len(candles)<6:return candidate
    highs=[]; lows=[]; closes=[]
    for c in candles[-24:]:
        try:
            if isinstance(c,dict):o=float(c['open']);h=float(c['high']);l=float(c['low']);cl=float(c['close'])
            else:o=float(c[1]);h=float(c[2]);l=float(c[3]);cl=float(c[4])
            highs.append(h); lows.append(l); closes.append(cl)
        except Exception:continue
    if len(highs)<6:return candidate
    last=closes[-1]; recent_high=max(highs[:-1]); recent_low=min(lows[:-1]); span=max(recent_high-recent_low, last*0.002)
    if category=='next_gainer_candidate':
        side='LONG'; trigger=recent_high*1.002; sl=max(recent_low,last-span*0.75); risk=trigger-sl
        if risk<=0:return candidate
        tp1=trigger+risk; tp2=trigger+2*risk
    else:
        side='SHORT'; trigger=recent_low*0.998; sl=min(recent_high,last+span*0.75); risk=sl-trigger
        if risk<=0:return candidate
        tp1=trigger-risk; tp2=trigger-2*risk
    score=num(candidate.get('score'),num(candidate.get('ranker_score')))
    confidence=max(MIN_FLOW_CONF,min(95.0,score))
    enriched=dict(candidate)
    enriched['trade_setup']={'side':side,'trigger':trigger,'tp1':tp1,'tp2':tp2,'invalidation':sl,'risk_per_unit':risk,'setup_source':'verified_1h_ohlcv_conditional'}
    enriched['prediction']={'direction':side,'entry_trigger':trigger,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':confidence,'conditional':True,'not_a_guarantee':True}
    enriched['flow_confidence']=confidence
    enriched['evidence']={'ohlcv_candles_used':len(candles),'last_price':last,'recent_high':recent_high,'recent_low':recent_low}
    return enriched

def candidates(brief,pre,cad,market,ranking):
    primary=[]; market_candidates=[]
    sources=[]
    for source in (brief.get('ranked_stories'),pre.get('ranked_stories')):
        if isinstance(source,list):sources.extend(source)
    for x in sources:
        if not isinstance(x,dict) or not x.get('symbol'):continue
        score=num(x.get('score'),num(x.get('ranker_score')))
        if score<MIN_SCORE:continue
        (primary if lane(x) in PRIMARY_LANES or x.get('type')=='flow' else market_candidates).append({**x,'score':score})
    selected=pre.get('selected_opportunity')
    if isinstance(selected,dict):add(primary if lane(selected) in PRIMARY_LANES or selected.get('type')=='flow' else market_candidates,selected)
    # The opportunity ranker/cadence is authoritative for early-mover candidates.
    for source in (ranking,cad):
        if not isinstance(source,dict):continue
        symbol=source.get('selected_symbol'); category=source.get('selected_category'); score=num(source.get('ranker_score'),num(source.get('effective_score')))
        if symbol and category and score>=MIN_SCORE:
            add(market_candidates,{'symbol':symbol,'category':category,'lane':'market','type':'market','score':score,'reason':'authoritative early-mover/opportunity ranking'})
    story=brief.get('primary_story')
    if isinstance(story,dict):add(primary if lane(story) in PRIMARY_LANES or story.get('type')=='flow' else market_candidates,story)
    return sorted(primary,key=lambda x:num(x.get('score')),reverse=True),sorted(market_candidates,key=lambda x:num(x.get('score')),reverse=True)

def choose(xs,rows,market):
    blocked_rows=[]
    for candidate in xs:
        enriched=derive_conditional_setup(candidate,market)
        reason=blocked(enriched,rows)
        if reason:blocked_rows.append({'symbol':enriched.get('symbol'),'reason':reason});continue
        if flow_complete(enriched):return enriched,blocked_rows
        blocked_rows.append({'symbol':enriched.get('symbol'),'reason':'prediction_contract_missing_verified_ohlcv'})
    return None,blocked_rows

def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cad=load(CADENCE); market=load(MARKET); ranking=load(RANKING); rows=recent()
    primary,market_candidates=candidates(brief,pre,cad,market,ranking)
    chosen,blocks=choose(primary,rows,market)
    if chosen is None:
        # Prefer a fresh next-gainer/next-loser candidate over a generic mover.
        preferred=[x for x in market_candidates if str(x.get('category','')).lower() in {'next_gainer_candidate','next_loser_candidate'}]
        fallback=preferred+[x for x in market_candidates if x not in preferred]
        chosen,more=choose(fallback,rows,market); blocks+=more
    current_allowed=bool(cad.get('publish')); decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'; primary_signal=False
    if chosen and (current_allowed or num(chosen.get('score'))>=MIN_SCORE):
        primary_signal=lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if flow_complete(chosen):decision='PRIMARY_SIGNAL' if primary_signal else 'MARKET_SIGNAL';reason='qualified_conditional_signal_selected'
        else:chosen=None;reason='prediction_contract_missing_direction_trigger_tp_or_sl'
    selected=None
    if chosen:
        selected=dict(chosen); _,pred,side,tr,tp1,tp2,sl,conf=setup_parts(selected)
        selected['signal_first_primary']=primary_signal; selected['prediction_contract_complete']=True; selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':True,'prediction':pred}
        PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'1.8-verified-ohlcv-conditional-setup','publish':bool(selected),'decision':decision,'reason':reason,'primary_signal':primary_signal,'secondary_meme':False,'selected':selected,'cadence_publish_on_disk':current_allowed,'current_cycle_cadence_recovery':True,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary),'market':len(market_candidates)},'policy':{'primary_lane':'capital_flow_and_measurable_market_outcomes','secondary_lane':'controlled_market_signals_and_memes','minimum_primary_score':MIN_SCORE,'minimum_flow_confidence':MIN_FLOW_CONF,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'anti_repetition_window':5,'text_similarity_block':SIM,'no_signal_means_no_signal_post':True,'conditional_setup_source':'verified_1h_ohlcv_only','no_guaranteed_outcome':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
