"""Signal-First Creator Router.

Measurable capital-flow/outcome opportunities are the primary publishing lane.
Memes remain a controlled secondary lane and cannot displace a qualified signal.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / 'data/live/editorial_preflight.json'
DIRECTOR = ROOT / 'data/live/content_director_brief.json'
CADENCE = ROOT / 'data/live/autonomous_cadence_6.json'
PUBLICATIONS = ROOT / 'analytics/publication_log.jsonl'
OUT = ROOT / 'data/live/signal_first_routing.json'
PRIMARY_LANES = {'flow', 'capital_flow_long', 'capital_flow_short', 'creator_signal_outcome', 'follow_up'}
MARKET_SIGNAL_LANES = {'market', 'top_gainers', 'top_losers', 'high_volatility', 'volume_leaders', 'technical_setup'}
MEME_LANES = {'crypto_meme', 'meme'}
MIN_PRIMARY_SCORE = float(os.getenv('SIGNAL_FIRST_MIN_SCORE', '72'))
MIN_FLOW_CONFIDENCE = float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE', '65'))
MEME_MAX_SHARE = float(os.getenv('SIGNAL_FIRST_MEME_MAX_SHARE', '0.25'))

def load(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value, dict) else {}
    except Exception: return {}

def num(value, default=0.0):
    try: return float(value)
    except Exception: return default

def lane(item):
    return str(item.get('lane') or item.get('type') or item.get('category') or '').lower()

def signal_candidate(brief, preflight):
    ranked = brief.get('ranked_stories') or []
    primary=[]; secondary=[]
    for item in ranked:
        if not isinstance(item, dict) or not item.get('symbol'): continue
        l=lane(item); score=num(item.get('score'))
        if score < MIN_PRIMARY_SCORE: continue
        if l in PRIMARY_LANES or item.get('type') == 'flow': primary.append(item)
        elif l in MARKET_SIGNAL_LANES or item.get('type') == 'market': secondary.append(item)
    selected = preflight.get('selected_opportunity') or {}
    if selected and str(selected.get('lane','')).lower() in PRIMARY_LANES | {'market','news'} and selected.get('symbol') and num(selected.get('score')) >= MIN_PRIMARY_SCORE:
        item={**selected,'score':num(selected.get('score')),'type':selected.get('lane')};
        (primary if str(item.get('lane') or '').lower() in PRIMARY_LANES else secondary).append(item)
    # Explicit priority: outcome proof/capital-flow first; ordinary market signals
    # are the next-best primary fallback. A stronger generic mover cannot displace
    # a qualified capital-flow thesis.
    if primary: return max(primary,key=lambda x:num(x.get('score')))
    return max(secondary,key=lambda x:num(x.get('score'))) if secondary else None

def flow_is_complete(item):
    setup=item.get('trade_setup') or {}
    return (str(setup.get('side') or '').upper() in {'LONG','SHORT'} and setup.get('trigger') is not None and setup.get('invalidation') is not None and num(item.get('flow_confidence'),num(item.get('score'))) >= MIN_FLOW_CONFIDENCE)

def meme_share():
    if not PUBLICATIONS.exists(): return 0.0,0,0
    rows=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-20:]:
        try:
            row=json.loads(line)
            if isinstance(row,dict): rows.append(row)
        except Exception: continue
    if not rows: return 0.0,0,0
    memes=sum(1 for r in rows if str(r.get('content_category') or r.get('category') or '').lower() in MEME_LANES)
    return memes/len(rows),memes,len(rows)

def main():
    preflight=load(PREFLIGHT); brief=load(DIRECTOR); cadence=load(CADENCE)
    candidate=signal_candidate(brief,preflight)
    cadence_publish=bool(cadence.get('publish',False))
    existing_category=str(cadence.get('selected_category') or cadence.get('category') or cadence.get('content_category') or '').lower()
    decision='NO_PUBLISH'; publish=False; selected=None; primary=False; meme=False; reason='no_qualified_primary_signal'
    if candidate and cadence_publish:
        selected=dict(candidate); primary=True; publish=True; decision='PRIMARY_SIGNAL'; reason='qualified_capital_flow_or_outcome_signal_selected'
        if candidate.get('type')=='flow' or lane(candidate) in {'flow','capital_flow_long','capital_flow_short'}:
            if not flow_is_complete(candidate):
                publish=False; primary=False; decision='NO_PUBLISH'; reason='flow_candidate_missing_trigger_or_invalidation'
        if publish:
            bound=dict(selected)
            side=str(bound.get('flow_side') or (bound.get('trade_setup') or {}).get('side') or '').upper()
            bound['category']=bound.get('category') or ('capital_flow_long' if side=='LONG' else 'capital_flow_short' if side=='SHORT' else 'creator_signal_outcome' if lane(bound)=='creator_signal_outcome' else 'top_gainers')
            bound['lane']=bound.get('lane') or bound.get('type'); bound['symbol']=str(bound.get('symbol') or '').upper(); bound['score']=num(bound.get('score')); bound['signal_first_primary']=True
            preflight['selected_opportunity']=bound
            preflight['signal_first_routing']={'decision':decision,'primary':True,'bound_symbol':bound['symbol'],'bound_category':bound['category']}
            PREFLIGHT.write_text(json.dumps(preflight,indent=2,ensure_ascii=False),encoding='utf-8')
    if not publish and cadence_publish and existing_category in MEME_LANES:
        share,memes,total=meme_share()
        if share < MEME_MAX_SHARE:
            meme=True; publish=True; decision='SECONDARY_MEME'; reason='no_qualified_primary_signal; controlled_meme_fallback'; selected={'category':'crypto_meme','lane':'meme','score':0,'symbol':'','primary_signal_available':False,'meme_share_before':round(share,3)}
        else:
            decision='MEME_QUOTA_BLOCKED'; reason=f'meme_share_limit_reached ({memes}/{total} >= {MEME_MAX_SHARE:.0%})'
    if not publish and cadence_publish and existing_category not in MEME_LANES:
        decision='CADENCE_NO_SIGNAL'; reason='cadence_allowed_cycle_but_no_primary_signal_met_threshold'
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'router_version':'1.2-signal-first','publish':publish,'decision':decision,'reason':reason,'primary_signal':primary,'secondary_meme':meme,'selected':selected,'cadence_publish':cadence_publish,'existing_category':existing_category,'policy':{'primary_lane':'capital_flow_and_measurable_market_outcomes','secondary_lane':'controlled_memes','primary_priority_order':['verified_outcome','capital_flow','market_signal'],'minimum_primary_score':MIN_PRIMARY_SCORE,'minimum_flow_confidence':MIN_FLOW_CONFIDENCE,'target_meme_share_max':MEME_MAX_SHARE,'meme_cannot_displace_qualified_signal':True,'meme_quota_is_rolling_20_publications':True,'no_signal_means_no_signal_post':True,'flow_requires_trigger_and_invalidation':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
