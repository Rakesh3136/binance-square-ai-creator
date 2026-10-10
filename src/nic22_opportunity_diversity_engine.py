"""NIC 22.1 — Opportunity Rotation + Professional Story Planner.

This layer sits after editorial_preflight and before opportunity freeze. It does
not invent market facts and does not rewrite the final post. It chooses among
already researched candidates and assigns a non-repeating story/chart format.
A recent asset is not allowed to win simply because its raw market score is high.
"""
from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path

PREFLIGHT=Path('data/live/editorial_preflight.json')
PUBLICATIONS=Path('analytics/publication_log.jsonl')
OUT=Path('data/live/nic22_opportunity_diversity.json')
SELECTION_OUT=Path('data/live/nic22_opportunity_selection.json')
CONFIRMATION_SELECTION=Path('data/live/nic22_3_confirmation_selection.json')
TRADE_LANES={'technical_setup','high_volatility','top_gainers','top_losers',
 'capital_flow_long','capital_flow_short','flow','conditional_trade',
 'creator_signal_outcome','follow_up','next_gainer_candidate','next_loser_candidate',
 'early_setup'}
ASSET_COOLDOWN_HOURS=72
ASSET_HARD_BLOCK_COUNT=2

STORY_TYPES={
    'breakout_retest': 'Breakout/reclaim: explain the level, confirmation condition and failed-break scenario.',
    'rejection_invalidation': 'Rejection: explain where the move failed, what confirms rejection and what invalidates it.',
    'range_structure': 'Range structure: explain boundaries, midpoint/context and what breaks the range thesis.',
    'trend_continuation': 'Trend continuation: explain market structure and what must hold for continuation.',
    'momentum_volume': 'Momentum/volume: explain the relationship between price movement and participation.',
    'relative_strength': 'Relative strength: compare the asset with a relevant benchmark without implying certainty.',
    'research_edge': 'Research edge: teach one evidence-backed observation readers can reuse.',
    'post_mortem_lesson': 'Post-mortem/lesson: extract a general market lesson from a verified setup or prior outcome.',
}
CHART_PROFILES={
    'breakout_retest':'breakout_retest_zones','rejection_invalidation':'rejection_and_invalidation','range_structure':'range_boundaries_midpoint','trend_continuation':'market_structure_swings','momentum_volume':'price_volume_relationship','relative_strength':'relative_strength_comparison','research_edge':'evidence_annotated_chart','post_mortem_lesson':'annotated_lesson_chart',
}

def load(path,default):
    try:
        v=json.loads(path.read_text(encoding='utf-8'))
        return v if isinstance(v,type(default)) else default
    except Exception:return default

def norm(s):
    return re.sub(r'[^A-Z0-9]','',str(s or '').upper()).replace('USDT','')

def symbols_from(row):
    vals=[row.get('symbol'),row.get('topic'),row.get('selected_lane_symbol')]
    return {norm(v) for v in vals if norm(v)}

def recent_rows():
    if not PUBLICATIONS.exists():return []
    cutoff=datetime.now(timezone.utc)-timedelta(hours=ASSET_COOLDOWN_HOURS)
    out=[]
    for line in PUBLICATIONS.read_text(encoding='utf-8',errors='replace').splitlines():
        try:
            r=json.loads(line)
            dt=datetime.fromisoformat(str(r.get('published_at','')).replace('Z','+00:00'))
            if dt>=cutoff:out.append((dt,r))
        except Exception:continue
    return out

def story_history(rows):
    types=Counter();charts=Counter();assets=Counter()
    for _,r in rows:
        for s in symbols_from(r):assets[s]+=1
        t=str(r.get('story_type') or r.get('content_category') or '').strip().lower()
        if t:types[t]+=1
        c=str(r.get('chart_profile') or r.get('visual_type') or '').strip().lower()
        if c:charts[c]+=1
    return assets,types,charts

def apply_confirmation_policy(eligible, confirmation):
    """Keep trade candidates aligned to NIC 22.3; never promote an unconfirmed setup."""
    status=str(confirmation.get('status') or '').upper()
    selected=confirmation.get('selected_opportunity') if isinstance(confirmation.get('selected_opportunity'),dict) else {}
    confirmed_symbol=norm(selected.get('symbol') or selected.get('topic'))
    if status=='CONFIRMED' and confirmed_symbol:
        aligned=[item for item in eligible
                 if confirmed_symbol in symbols_from(item[1])]
        return aligned, 'confirmed_symbol_authoritative' if aligned else 'confirmed_symbol_not_in_eligible_pool'
    safe=[]
    for score,candidate in eligible:
        lane=str(candidate.get('category') or candidate.get('type') or '').strip().lower().replace(' ','_')
        if lane not in TRADE_LANES:
            safe.append((score,candidate))
    return safe, 'no_confirmed_trade_candidate; editorial_only' if safe else 'no_confirmed_candidate; trade_publication_blocked'

def choose_story(candidate, recent_types, recent_charts):
    lane=str(candidate.get('category') or candidate.get('type') or '').lower()
    move=float(candidate.get('price_change_percent') or 0)
    flow=bool(candidate.get('flow_side'))
    if flow or abs(move)>=8: preferred=['momentum_volume','breakout_retest','rejection_invalidation','range_structure']
    elif 'news' in lane: preferred=['research_edge','trend_continuation','rejection_invalidation','relative_strength']
    elif abs(move)>=3: preferred=['trend_continuation','range_structure','breakout_retest','momentum_volume']
    else: preferred=['research_edge','relative_strength','range_structure','post_mortem_lesson']
    for s in preferred+list(STORY_TYPES):
        if s not in recent_types and CHART_PROFILES[s] not in recent_charts:return s
    for s in preferred+list(STORY_TYPES):
        if s not in recent_types:return s
    return preferred[0]

def main():
    pre=load(PREFLIGHT,{})
    candidates=pre.get('candidate_pool') if isinstance(pre.get('candidate_pool'),list) else []
    recent=recent_rows();assets,types,charts=story_history(recent)
    eligible=[]
    for c in candidates:
        if not isinstance(c,dict):continue
        symbol=norm(c.get('topic') or c.get('symbol'))
        if not symbol:continue
        count=assets.get(symbol,0)
        if count>=ASSET_HARD_BLOCK_COUNT:continue
        if c.get('cooldown_active') is True:continue
        score=float(c.get('adjusted_score') or 0)
        diversity=25 if count==0 else 8
        diversity-=min(15,types.get(str(c.get('category','')).lower(),0)*5)
        eligible.append((score+diversity,c))
    eligible.sort(key=lambda x:x[0],reverse=True)
    confirmation=load(CONFIRMATION_SELECTION,{})
    eligible, confirmation_reason=apply_confirmation_policy(eligible,confirmation)
    chosen=eligible[0][1] if eligible else None
    reason=('rotated_to_unused_or_underused_asset' if chosen else 'no_diverse_eligible_asset')
    if confirmation_reason != 'confirmed_symbol_authoritative':
        reason=confirmation_reason
    selected=None
    if chosen:
        story=choose_story(chosen,types,charts)
        selected={'category':chosen.get('category'),'symbol':chosen.get('topic') or chosen.get('symbol'),'reason':chosen.get('reason'),'lane':chosen.get('type'),'score':chosen.get('adjusted_score'),'story_type':story,'story_instruction':STORY_TYPES[story],'chart_profile':CHART_PROFILES[story],'asset_recent_count':assets.get(norm(chosen.get('topic') or chosen.get('symbol')),0),'editorial_structure_family':story,'instruction':('Use this frozen opportunity and story type. The post must teach a concrete market-reading idea, distinguish observations from scenarios, state what would invalidate the thesis, and avoid guarantees. Do not reuse a recent sentence, hook family, CTA pattern, or chart composition.')}
        for k in ('news_title','news_url','news_source','news_published_at','news_score','news_symbols','flow_side','flow_confidence','trade_setup','relative_strength_to_btc','flow_proxy_score','flow_notes'):
            if k in chosen:selected[k]=chosen[k]
    result={'version':'22.1-opportunity-rotation','generated_at':datetime.now(timezone.utc).isoformat(),'status':'SELECTED' if selected else 'BLOCKED','reason':reason,'selected_opportunity':selected,'recent_asset_counts':dict(assets),'recent_story_types':dict(types),'recent_chart_profiles':dict(charts),'candidate_count':len(candidates),'eligible_count':len(eligible),'rules':{'asset_cooldown_hours':ASSET_COOLDOWN_HOURS,'asset_hard_block_count':ASSET_HARD_BLOCK_COUNT,'no_diverse_asset_fallback':True,'no_fact_invention':True,'no_publish_bypass':True,'nic22_3_confirmation_authoritative':True,'confirmation_policy':confirmation_reason}}
    pre['selected_opportunity']=selected
    pre['run_ai']=bool(selected)
    pre['reason']='nic22_diverse_opportunity_selected' if selected else reason
    pre['nic22']=result
    PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(result,indent=2,ensure_ascii=False)
    OUT.write_text(payload,encoding='utf-8')
    SELECTION_OUT.write_text(payload,encoding='utf-8')
    print(payload)
    return 0 if selected else 1

if __name__=='__main__':raise SystemExit(main())
