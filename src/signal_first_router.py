"""Signal-First Creator Router + anti-repetition guard.

Qualified capital-flow/outcome predictions are the primary publishing lane.
Every prediction must carry direction, trigger, TP1/TP2 and SL/invalidation.
Recent repetition can block a candidate, but it can never force a meme over a
qualified alternative signal.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; CADENCE=ROOT/'data/live/autonomous_cadence_6.json'; PUBLICATIONS=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/signal_first_routing.json'
PRIMARY_LANES={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}
MARKET_SIGNAL_LANES={'market','top_gainers','top_losers','high_volatility','volume_leaders','technical_setup'}
MEME_LANES={'crypto_meme','meme'}
MIN_PRIMARY_SCORE=float(os.getenv('SIGNAL_FIRST_MIN_SCORE','72')); MIN_FLOW_CONFIDENCE=float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE','65')); MEME_MAX_SHARE=float(os.getenv('SIGNAL_FIRST_MEME_MAX_SHARE','0.25')); TEXT_SIMILARITY_BLOCK=float(os.getenv('SIGNAL_FIRST_TEXT_SIMILARITY','0.72'))

def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}

def num(v,d=0.0):
    try:return float(v)
    except Exception:return d

def lane(item): return str(item.get('lane') or item.get('type') or item.get('category') or '').lower()

def recent_rows():
    if not PUBLICATIONS.exists():return []
    rows=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            r=json.loads(line)
            if isinstance(r,dict) and r.get('status')=='PUBLISHED_AUTONOMOUSLY':rows.append(r)
        except Exception:pass
    return rows[-20:]

def norm_text(v):
    s=re.sub(r'\$?[0-9]+(?:\.[0-9]+)?',' ',str(v or '').lower()); s=re.sub(r'[^a-z0-9 ]+',' ',s); return re.sub(r'\s+',' ',s).strip()

def text_of(row): return row.get('post') or row.get('text') or row.get('content') or row.get('draft') or row.get('body') or ''

def thesis_key(item):
    setup=item.get('trade_setup') or {}; pred=item.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or item.get('flow_side') or '').upper()
    return f"{str(item.get('symbol') or '').upper()}|{side}|{str(item.get('category') or lane(item))}|{str(item.get('trigger') or setup.get('trigger') or pred.get('entry_trigger') or '')}|{str(item.get('invalidation') or setup.get('invalidation') or pred.get('sl') or '')}"

def repetition_blocked(item,rows):
    symbol=str(item.get('symbol') or '').upper(); key=thesis_key(item); setup=item.get('trade_setup') or {}; side=str(setup.get('side') or (item.get('prediction') or {}).get('direction') or '').upper()
    for r in rows[-5:]:
        rs=str(r.get('symbol') or '').upper(); rside=str(r.get('direction') or r.get('side') or r.get('flow_side') or '').upper()
        if symbol and rs==symbol and side and rside==side:return True,'same_symbol_and_direction_recent'
        old_key=str(r.get('thesis_key') or '')
        if old_key and old_key==key:return True,'same_thesis_key_recent'
        old=norm_text(text_of(r)); new=norm_text(item.get('post') or item.get('draft') or '')
        if new and old and SequenceMatcher(None,new,old).ratio()>=TEXT_SIMILARITY_BLOCK:return True,'high_text_similarity_recent'
    return False,''

def flow_is_complete(item):
    setup=item.get('trade_setup') or {}; pred=item.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or '').upper(); trigger=setup.get('trigger',pred.get('entry_trigger')); tp1=setup.get('tp1',pred.get('tp1')); tp2=setup.get('tp2',pred.get('tp2')); sl=setup.get('invalidation',pred.get('sl')); conf=num(item.get('flow_confidence'),num((item.get('multitimeframe') or {}).get('confidence'),num(item.get('score'))))
    return side in {'LONG','SHORT'} and trigger is not None and tp1 is not None and tp2 is not None and sl is not None and conf>=MIN_FLOW_CONFIDENCE

def meme_share():
    rows=recent_rows()
    if not rows:return 0.0,0,0
    memes=sum(1 for r in rows if str(r.get('content_category') or r.get('category') or '').lower() in MEME_LANES); return memes/len(rows),memes,len(rows)

def signal_candidates(brief,preflight):
    primary=[]; secondary=[]
    for item in brief.get('ranked_stories') or []:
        if not isinstance(item,dict) or not item.get('symbol'):continue
        score=num(item.get('score')); l=lane(item)
        if score<MIN_PRIMARY_SCORE:continue
        (primary if l in PRIMARY_LANES or item.get('type')=='flow' else secondary if l in MARKET_SIGNAL_LANES or item.get('type')=='market' else []).append(item)
    selected=preflight.get('selected_opportunity') or {}
    if selected and selected.get('symbol') and num(selected.get('score'))>=MIN_PRIMARY_SCORE:
        (primary if lane(selected) in PRIMARY_LANES else secondary).append({**selected,'score':num(selected.get('score'))})
    return sorted(primary,key=lambda x:num(x.get('score')),reverse=True),sorted(secondary,key=lambda x:num(x.get('score')),reverse=True)

def choose(candidates,rows):
    blocked=[]
    for item in candidates:
        ok,reason=repetition_blocked(item,rows)
        if not ok:return item,blocked
        blocked.append({'symbol':item.get('symbol'),'reason':reason})
    return None,blocked

def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); cadence=load(CADENCE); rows=recent_rows(); primary_candidates,secondary_candidates=signal_candidates(brief,pre)
    candidate,blocked=choose(primary_candidates,rows)
    if candidate is None: candidate,secondary_blocked=choose(secondary_candidates,rows); blocked += secondary_blocked
    cadence_publish=bool(cadence.get('publish')); existing_category=str(cadence.get('selected_category') or cadence.get('category') or cadence.get('content_category') or '').lower()
    publish=False; decision='NO_PUBLISH'; primary=False; meme=False; selected=None; reason='no_qualified_non_repetitive_signal'
    if candidate and cadence_publish:
        selected=dict(candidate); primary=True; publish=True; decision='PRIMARY_SIGNAL'; reason='qualified_non_repetitive_signal_selected'
        if lane(candidate) in PRIMARY_LANES or candidate.get('type')=='flow':
            if not flow_is_complete(candidate):publish=False;primary=False;decision='NO_PUBLISH';reason='prediction_contract_missing_direction_trigger_tp_or_sl'
        if publish:
            bound=dict(selected); setup=bound.get('trade_setup') or {}; pred=bound.get('prediction') or {}; side=str(setup.get('side') or pred.get('direction') or '').upper(); bound['category']=bound.get('category') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short' if side=='SHORT' else 'creator_signal_outcome'); bound['lane']=bound.get('lane') or bound.get('type'); bound['symbol']=str(bound.get('symbol') or '').upper(); bound['score']=num(bound.get('score')); bound['signal_first_primary']=True; bound['prediction_contract_complete']=True; bound['thesis_key']=thesis_key(bound); pre['selected_opportunity']=bound; pre['signal_first_routing']={'decision':decision,'primary':True,'bound_symbol':bound['symbol'],'bound_category':bound['category'],'prediction':pred or {'direction':side,'entry_trigger':setup.get('trigger'),'tp1':setup.get('tp1'),'tp2':setup.get('tp2'),'sl':setup.get('invalidation')}}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    if not publish and cadence_publish and existing_category in MEME_LANES:
        share,memes,total=meme_share()
        if share<MEME_MAX_SHARE:
            meme=True;publish=True;decision='SECONDARY_MEME';reason='no_qualified_primary_signal; controlled_meme_fallback';selected={'category':'crypto_meme','lane':'meme','score':0,'symbol':'','primary_signal_available':False,'meme_share_before':round(share,3)}
        else:decision='MEME_QUOTA_BLOCKED';reason=f'meme_share_limit_reached ({memes}/{total} >= {MEME_MAX_SHARE:.0%})'
    if not publish and cadence_publish and existing_category not in MEME_LANES:decision='CADENCE_NO_SIGNAL';reason=reason if blocked else 'cadence_allowed_cycle_but_no_primary_signal_met_threshold'
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'1.3-signal-first-diversity-prediction','publish':publish,'decision':decision,'reason':reason,'primary_signal':primary,'secondary_meme':meme,'selected':selected,'cadence_publish':cadence_publish,'existing_category':existing_category,'blocked_candidates':blocked,'policy':{'primary_lane':'capital_flow_and_measurable_market_outcomes','secondary_lane':'controlled_memes','primary_priority_order':['verified_outcome','capital_flow','market_signal'],'minimum_primary_score':MIN_PRIMARY_SCORE,'minimum_flow_confidence':MIN_FLOW_CONFIDENCE,'prediction_required':['direction','entry_trigger','tp1','tp2','sl','confidence'],'target_meme_share_max':MEME_MAX_SHARE,'meme_cannot_displace_qualified_signal':True,'meme_quota_is_rolling_20_publications':True,'no_signal_means_no_signal_post':True,'anti_repetition_window':5,'text_similarity_block':TEXT_SIMILARITY_BLOCK}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
