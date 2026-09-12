"""Content Portfolio Manager: stop repetitive single-asset publishing.

This stage operates after opportunity ranking and before the authoritative
opportunity is frozen. It chooses among researched candidates while optimizing
for story diversity, asset diversity, thesis freshness and reader value.
Early-mover candidates are conditional hypotheses and must never be presented
as guaranteed future gainers/losers.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json';DIRECTOR=ROOT/'data/live/content_director_brief.json';LOG=ROOT/'analytics/publication_log.jsonl';OUT=ROOT/'data/live/content_portfolio_guard.json'
MIN_SCORE=float(os.getenv('PORTFOLIO_MIN_SCORE','68'));RECENT_WINDOW=int(os.getenv('PORTFOLIO_RECENT_WINDOW','12'));BTC_MAX_RECENT=int(os.getenv('PORTFOLIO_BTC_MAX_RECENT','1'));ASSET_MAX_RECENT=int(os.getenv('PORTFOLIO_ASSET_MAX_RECENT','2'));SIMILARITY_BLOCK=float(os.getenv('PORTFOLIO_SIMILARITY_BLOCK','0.58'))
PRIMARY={'creator_signal_outcome','capital_flow_long','capital_flow_short','follow_up','technical_setup','top_gainers','top_losers','high_volatility','volume_leaders','next_gainer_candidate','next_loser_candidate'}
NON_SIGNAL={'breaking_news','news_and_macro','watchlist','comparison','education','crypto_meme'}
STOPWORDS={'the','a','an','and','or','to','of','for','in','on','with','from','as','is','are','this','that','it','its','at','by','be','has','have','will','can','now','why','what','how','than','into','after','over','under','market','crypto','price','today','latest','update','binance'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def num(v,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d
def symbol(v):
    return str(v or '').upper().replace('BINANCE:','').replace('$','').strip().removesuffix('USDT')
def category(item):return str(item.get('category') or item.get('lane') or item.get('content_category') or item.get('type') or '').lower()
def lane_priority(cat):
    if cat in PRIMARY:return 2
    if cat in NON_SIGNAL:return 1 if cat!='crypto_meme' else 0
    return 1
def words(text):return {x for x in re.findall(r'[a-z0-9]{3,}',str(text or '').lower()) if x not in STOPWORDS}
def similarity(left,right):
    a,b=words(left),words(right)
    return len(a&b)/max(1,len(a|b)) if a and b else 0.0
def text_of(item):
    parts=[item.get('topic'),item.get('title'),item.get('news_title'),item.get('hook'),item.get('reason'),item.get('editorial_style')]
    setup=item.get('trade_setup') or {};parts.extend([setup.get('side'),str(setup.get('trigger')),str(setup.get('invalidation')),str(item.get('evidence') or '')])
    return ' '.join(str(x or '') for x in parts if x)
def recent_publications():
    if not LOG.exists():return []
    rows=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-160:]:
        try:row=json.loads(line)
        except Exception:continue
        if isinstance(row,dict) and row.get('status')=='PUBLISHED_AUTONOMOUSLY':rows.append(row)
    return rows[-RECENT_WINDOW:]
def asset_counts(rows):
    counts={}
    for row in rows:
        for raw in (row.get('symbol'),row.get('selected_lane_symbol')):
            s=symbol(raw)
            if s:counts[s]=counts.get(s,0)+1;break
    return counts
def recent_same_category(rows,cat):return sum(1 for r in rows[-5:] if category(r)==cat)
def is_material_followup(candidate):
    cat=category(candidate)
    return cat in {'creator_signal_outcome','follow_up'} and bool(candidate.get('proof_status') or candidate.get('outcome') or candidate.get('outcome_status') or candidate.get('new_evidence') or candidate.get('next_hook'))
def news_asset_evidence(candidate):
    cat=category(candidate)
    if cat not in {'breaking_news','news_and_macro','news_market_impact','news'}:return True
    title=str(candidate.get('title') or candidate.get('news_title') or '').lower();summary=str(candidate.get('summary') or '').lower();s=symbol(candidate.get('symbol')).lower()
    if not s:return False
    aliases={'btc':['bitcoin','$btc','btc'],'eth':['ethereum','$eth','eth','ether'],'bnb':['bnb','binance coin'],'sol':['solana','$sol','sol'],'xrp':['xrp','ripple'],'doge':['dogecoin','$doge','doge']}
    names=aliases.get(s,[f'${s}',s]);return any(re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',title+' '+summary) for name in names)
def candidate_key(item):return f'{symbol(item.get("symbol"))}|{category(item)}|{str(item.get("type") or "").lower()}'
def main():
    pre=load(PREFLIGHT);brief=load(DIRECTOR);ranked=brief.get('ranked_stories') or [];current=pre.get('selected_opportunity') or {};current=current if isinstance(current,dict) else {};recent=recent_publications();counts=asset_counts(recent);recent_texts=[text_of(r) for r in recent[-8:]];ranked=[x for x in ranked if isinstance(x,dict) and symbol(x.get('symbol'))]
    # opportunity_ranker_6.4 may add early-mover candidates directly to preflight;
    # include that ranked list so portfolio policy can select them before freeze.
    ranking=pre.get('opportunity_ranking_6') or {};ranked_extra=ranking.get('top_candidates') or [];ranked += [x for x in ranked_extra if isinstance(x,dict) and symbol(x.get('symbol')) and x.get('early_mover')]
    evaluated=[];seen=set()
    for raw in ranked:
        s=symbol(raw.get('symbol'));cat=category(raw);key=candidate_key(raw)
        if key in seen:continue
        seen.add(key);score=num(raw.get('ranker_score') or raw.get('score'))
        if score<MIN_SCORE:continue
        reasons=[];hard_block=False;count=counts.get(s,0);material_followup=is_material_followup(raw);priority=lane_priority(cat)
        if not news_asset_evidence(raw):hard_block=True;reasons.append('news_asset_not_explicitly_supported')
        if s=='BTC' and count>=BTC_MAX_RECENT and not material_followup:hard_block=True;reasons.append(f'btc_overexposed_{count}_recent_posts')
        elif count>=ASSET_MAX_RECENT and not material_followup:hard_block=True;reasons.append(f'asset_overexposed_{count}_recent_posts')
        same_cat=recent_same_category(recent,cat)
        if same_cat>=2 and cat not in {'creator_signal_outcome','follow_up'}:score-=6;reasons.append('category_repeat_penalty')
        candidate_text=text_of(raw);max_sim=max((similarity(candidate_text,t) for t in recent_texts),default=0.0)
        if max_sim>=SIMILARITY_BLOCK and not material_followup:hard_block=True;reasons.append(f'semantic_similarity_{max_sim:.2f}')
        if count==0:score+=7;reasons.append('new_asset_bonus')
        if priority==2:score+=8;reasons.append('primary_signal_lane_bonus')
        if cat in {'capital_flow_long','capital_flow_short'} and num(raw.get('flow_confidence'))>=70:score+=5;reasons.append('high_flow_confidence_bonus')
        if cat in {'next_gainer_candidate','next_loser_candidate'}:
            if raw.get('confirmation_required',True):reasons.append('early_mover_confirmation_required')
            score+=3;reasons.append('early_mover_discovery_bonus')
        evaluated.append({'candidate':raw,'score_before_guard':round(num(raw.get('ranker_score') or raw.get('score')),2),'portfolio_score':round(score,2),'lane_priority':priority,'asset_recent_count':count,'recent_same_category':same_cat,'max_recent_semantic_similarity':round(max_sim,3),'hard_block':hard_block,'reasons':reasons})
    allowed=[x for x in evaluated if not x['hard_block']]
    evaluated.sort(key=lambda x:(not x['hard_block'],x['lane_priority'],x['portfolio_score']),reverse=True);allowed.sort(key=lambda x:(x['lane_priority'],x['portfolio_score']),reverse=True);chosen_entry=allowed[0] if allowed else None;chosen=chosen_entry['candidate'] if chosen_entry else None
    if current and category(current) in {'creator_signal_outcome','follow_up'} and is_material_followup(current):chosen=current;decision='PROTECTED_OUTCOME_OR_FOLLOWUP';reason='material_outcome_update_is_allowed_to_revisit_a_recent_asset';chosen_entry=None
    elif chosen:decision='DIVERSIFIED_STORY_SELECTED';reason='portfolio_manager_selected_the_best_non_repetitive_candidate'
    else:decision='WAIT_FOR_DIFFERENT_STORY';reason='all_qualified_candidates_are_repetitive_or_unsupported'
    publish=chosen is not None
    if publish:
        chosen=dict(chosen);chosen['portfolio_guard_selected']=True;chosen['portfolio_score']=round(chosen_entry['portfolio_score'],2) if chosen_entry else num(chosen.get('score'));chosen['symbol']=symbol(chosen.get('symbol'))+'USDT';pre['selected_opportunity']=chosen;pre['content_portfolio_guard']={'decision':decision,'reason':reason,'selected_symbol':symbol(chosen.get('symbol')),'selected_category':category(chosen),'recent_asset_counts':counts,'recent_window':len(recent)};brief['authoritative_selection']=chosen;brief['portfolio_guard']=pre['content_portfolio_guard'];DIRECTOR.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8');PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    else:
        pre['selected_opportunity']={};pre['content_portfolio_guard']={'decision':decision,'reason':reason,'recent_asset_counts':counts,'recent_window':len(recent)};PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'version':'1.2-next-mover-portfolio','publish':publish,'decision':decision,'reason':reason,'selected':chosen,'recent_asset_counts':counts,'recent_window':len(recent),'candidates_considered':len(evaluated),'blocked_candidates':[x for x in evaluated if x['hard_block']][:12],'top_allowed_candidates':allowed[:12],'policy':{'btc_max_recent_posts':BTC_MAX_RECENT,'asset_max_recent_posts':ASSET_MAX_RECENT,'recent_window':RECENT_WINDOW,'semantic_similarity_block':SIMILARITY_BLOCK,'generic_news_cannot_create_btc_fallback':True,'signal_lane_priority_over_generic_news':True,'early_mover_lanes_enabled':True,'early_mover_requires_confirmation':True,'wait_when_repetitive':True,'outcome_followups_can_revisit_asset':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
