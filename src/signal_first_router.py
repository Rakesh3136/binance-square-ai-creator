"""Signal-first routing with authoritative current-cycle recovery."""
from __future__ import annotations
import json,os,re
from datetime import datetime,timezone
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; CADENCE=ROOT/'data/live/autonomous_cadence_6.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/signal_first_routing.json'
PRIMARY_LANES={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}
MARKET_LANES={'market','top_gainers','top_losers','high_volatility','volume_leaders','technical_setup','next_gainer_candidate','next_loser_candidate'}
MIN_SCORE=float(os.getenv('SIGNAL_FIRST_MIN_SCORE','72')); MIN_FLOW_CONF=float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE','65')); SIM=float(os.getenv('SIGNAL_FIRST_TEXT_SIMILARITY','0.72'))
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def num(x,d=0.0):
    try:return float(x)
    except Exception:return d
def lane(x): return str(x.get('lane') or x.get('type') or x.get('category') or '').lower()
def recent():
    if not PUBLICATIONS.exists():return []
    good={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_SUBMITTED_504'}; out=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-120:]:
        try:
            r=json.loads(line)
            if isinstance(r,dict) and r.get('status') in good:out.append(r)
        except Exception:pass
    return out[-20:]
def text(x):return x.get('post') or x.get('text') or x.get('content') or x.get('draft') or x.get('body') or ''
def setup_parts(x):
    s=x.get('trade_setup') if isinstance(x.get('trade_setup'),dict) else {}; p=x.get('prediction') if isinstance(x.get('prediction'),dict) else {}
    side=str(s.get('side') or p.get('direction') or x.get('flow_side') or '').upper(); trigger=s.get('trigger',p.get('entry_trigger')); tp1=s.get('tp1',p.get('tp1')); tp2=s.get('tp2',p.get('tp2')); sl=s.get('invalidation',p.get('sl')); conf=num(x.get('flow_confidence'),num((x.get('multitimeframe') or {}).get('confidence'),num(x.get('score'))))
    return s,p,side,trigger,tp1,tp2,sl,conf
def flow_complete(x):
    _,_,side,tr,tp1,tp2,sl,conf=setup_parts(x); return side in {'LONG','SHORT'} and tr is not None and tp1 is not None and tp2 is not None and sl is not None and conf>=MIN_FLOW_CONF
def norm(x):
    x=re.sub(r'\$?[0-9]+(?:\.[0-9]+)?',' ',str(x or '').lower()); return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]+',' ',x)).strip()
def blocked(x,rows):
    sym=str(x.get('symbol') or '').upper(); _,_,side,_,_,_,_,_=setup_parts(x)
    for r in rows[-5:]:
        rs=str(r.get('symbol') or '').upper(); rside=str(r.get('direction') or r.get('side') or r.get('flow_side') or '').upper()
        if sym and rs==sym and side and rside==side:return 'same_symbol_and_direction_recent'
        old=norm(text(r)); new=norm(text(x))
        if new and old and SequenceMatcher(None,new,old).ratio()>=SIM:return 'high_text_similarity_recent'
    return ''
def add(target,x):
    if not isinstance(x,dict) or not x.get('symbol'):return
    score=num(x.get('score'),num(x.get('ranker_score')))
    if score>=MIN_SCORE:target.append({**x,'score':score})
def candidates(brief,pre,cad):
    primary_candidates=[]; market_candidates=[]
    for x in (brief.get('ranked_stories') or []):
        if not isinstance(x,dict):continue
        l=lane(x); score=num(x.get('score'))
        if not x.get('symbol') or score<MIN_SCORE:continue
        if l in PRIMARY_LANES or x.get('type')=='flow':primary_candidates.append(x)
        elif l in MARKET_LANES or x.get('type')=='market':market_candidates.append(x)
    for x in (pre.get('ranked_stories') or []):
        if not isinstance(x,dict):continue
        l=lane(x); score=num(x.get('score'),num(x.get('ranker_score')))
        if x.get('symbol') and score>=MIN_SCORE:(primary_candidates if l in PRIMARY_LANES or x.get('type')=='flow' else market_candidates).append({**x,'score':score})
    selected=pre.get('selected_opportunity')
    add(primary_candidates if isinstance(selected,dict) and (lane(selected) in PRIMARY_LANES or selected.get('type')=='flow') else market_candidates,selected or {})
    cs={'symbol':cad.get('selected_symbol'),'category':cad.get('selected_category'),'score':num(cad.get('effective_score'),num(cad.get('ranker_score'))),'type':'market','lane':'market','reason':'current cadence selected opportunity'}; add(market_candidates,cs)
    story=brief.get('primary_story')
    if isinstance(story,dict):add(primary_candidates if lane(story) in PRIMARY_LANES or story.get('type')=='flow' else market_candidates,story)
    return sorted(primary_candidates,key=lambda x:num(x.get('score')),reverse=True),sorted(market_candidates,key=lambda x:num(x.get('score')),reverse=True)
def choose(xs,rows):
    blocked_rows=[]
    for x in xs:
        reason=blocked(x,rows)
        if not reason:return x,blocked_rows
        blocked_rows.append({'symbol':x.get('symbol'),'reason':reason})
    return None,blocked_rows
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cad=load(CADENCE); rows=recent(); primary_candidates,market_candidates=candidates(brief,pre,cad)
    chosen,blocks=choose(primary_candidates,rows)
    if chosen is None:
        market_choice,more=choose(market_candidates,rows); blocks+=more
        if market_choice is not None and not flow_complete(market_choice):
            blocks.append({'symbol':market_choice.get('symbol'),'reason':'market_fallback_requires_prediction_contract'})
            market_choice=None
        chosen=market_choice
    current_allowed=bool(cad.get('publish')); is_primary_signal=False; decision='NO_PUBLISH'; reason='no_qualified_non_repetitive_signal'
    if chosen and (current_allowed or num(chosen.get('score'))>=MIN_SCORE):
        is_primary_signal=lane(chosen) in PRIMARY_LANES or chosen.get('type')=='flow'
        if not flow_complete(chosen):chosen=None; is_primary_signal=False; reason='prediction_contract_missing_direction_trigger_tp_or_sl'
        else:decision='PRIMARY_SIGNAL' if is_primary_signal else 'MARKET_SIGNAL';reason='qualified_prediction_signal_selected'
    publish=chosen is not None; selected=None
    if chosen:
        selected=dict(chosen); _,p,side,tr,tp1,tp2,sl,conf=setup_parts(selected); selected['signal_first_primary']=is_primary_signal; selected['prediction_contract_complete']=flow_complete(selected); selected['thesis_key']=f"{selected.get('symbol','')}|{side}|{selected.get('category',lane(selected))}|{tr}|{sl}"
        pre['selected_opportunity']=selected; pre['signal_first_routing']={'decision':decision,'primary':is_primary_signal,'bound_symbol':str(selected.get('symbol') or '').upper(),'bound_category':selected.get('category') or lane(selected),'prediction_contract_complete':selected['prediction_contract_complete'],'prediction':p}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'1.7-prediction-contract-fallback-gate','publish':publish,'decision':decision,'reason':reason,'primary_signal':is_primary_signal,'secondary_meme':False,'selected':selected,'cadence_publish_on_disk':current_allowed,'current_cycle_cadence_recovery':True,'blocked_candidates':blocks,'candidate_counts':{'primary':len(primary_candidates),'market':len(market_candidates)},'policy':{'primary_lane':'capital_flow_and_measurable_market_outcomes','secondary_lane':'controlled_market_signals_and_memes','minimum_primary_score':MIN_SCORE,'minimum_flow_confidence':MIN_FLOW_CONF,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'anti_repetition_window':5,'text_similarity_block':SIM,'no_signal_means_no_signal_post':True,'market_fallback_requires_prediction_contract':True,'cadence_current_cycle_is_authoritative':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
