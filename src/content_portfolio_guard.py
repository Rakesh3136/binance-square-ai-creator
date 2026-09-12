"""Portfolio guard with publication-truth-aware deduplication."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; LOG=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/content_portfolio_guard.json'
MIN_SCORE=float(os.getenv('PORTFOLIO_MIN_SCORE','68')); RECENT_WINDOW=int(os.getenv('PORTFOLIO_RECENT_WINDOW','12')); BTC_MAX_RECENT=int(os.getenv('PORTFOLIO_BTC_MAX_RECENT','1')); ASSET_MAX_RECENT=int(os.getenv('PORTFOLIO_ASSET_MAX_RECENT','1')); SIMILARITY_BLOCK=float(os.getenv('PORTFOLIO_SIMILARITY_BLOCK','0.58')); SAME_ASSET_HOURS=float(os.getenv('PORTFOLIO_SAME_ASSET_HOURS','6'))
PRIMARY={'creator_signal_outcome','capital_flow_long','capital_flow_short','follow_up','technical_setup','top_gainers','top_losers','high_volatility','volume_leaders','next_gainer_candidate','next_loser_candidate'}
NON_SIGNAL={'breaking_news','news_and_macro','watchlist','comparison','education','crypto_meme'}
STOPWORDS={'the','a','an','and','or','to','of','for','in','on','with','from','as','is','are','this','that','it','its','at','by','be','has','have','will','can','now','why','what','how','than','into','after','over','under','market','crypto','price','today','latest','update','binance'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}
def num(v,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d
def symbol(v):return str(v or '').upper().replace('BINANCE:','').replace('$','').strip().removesuffix('USDT')
def category(item):return str(item.get('category') or item.get('lane') or item.get('content_category') or item.get('type') or '').lower()
def lane_priority(cat):return 2 if cat in PRIMARY else (0 if cat=='crypto_meme' else 1)
def words(text):return {x for x in re.findall(r'[a-z0-9]{3,}',str(text or '').lower()) if x not in STOPWORDS}
def similarity(a,b):
    x,y=words(a),words(b); return len(x&y)/max(1,len(x|y)) if x and y else 0.0
def text_of(item):
    setup=item.get('trade_setup') or {}; return ' '.join(str(x or '') for x in [item.get('topic'),item.get('title'),item.get('news_title'),item.get('hook'),item.get('reason'),item.get('editorial_style'),setup.get('side'),setup.get('trigger'),setup.get('invalidation'),item.get('evidence')])
def parse_time(row):
    raw=row.get('published_at') or row.get('timestamp') or ''
    try:return datetime.fromisoformat(str(raw).replace('Z','+00:00'))
    except Exception:return None
def recent_publications():
    if not LOG.exists():return []
    accepted={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','PUBLISHED_SUBMITTED_504','VERIFIED_PUBLISHED'}
    rows=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-300:]:
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict) and str(r.get('status') or '') in accepted: rows.append(r)
    return rows[-RECENT_WINDOW:]
def asset_counts(rows):
    out={}
    for r in rows:
        s=symbol(r.get('symbol') or r.get('selected_lane_symbol'))
        if s:out[s]=out.get(s,0)+1
    return out
def material_followup(c):
    return category(c) in {'creator_signal_outcome','follow_up'} and bool(c.get('proof_status') or c.get('outcome') or c.get('outcome_status') or c.get('new_evidence') or c.get('next_hook'))
def news_supported(c):
    if category(c) not in {'breaking_news','news_and_macro','news_market_impact','news'}:return True
    s=symbol(c.get('symbol')).lower(); blob=(str(c.get('title') or '')+' '+str(c.get('news_title') or '')+' '+str(c.get('summary') or '')).lower()
    return bool(s) and bool(re.search(r'(?<![a-z0-9])(?:\$?'+re.escape(s)+r')(?![a-z0-9])',blob))
def candidate_key(c):return f'{symbol(c.get("symbol"))}|{category(c)}|{str(c.get("type") or "").lower()}'
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); current=pre.get('selected_opportunity') or {}; current=current if isinstance(current,dict) else {}; recent=recent_publications(); counts=asset_counts(recent); recent_texts=[text_of(r) for r in recent[-8:]]
    ranked=[x for x in (brief.get('ranked_stories') or []) if isinstance(x,dict) and symbol(x.get('symbol'))]
    extra=(pre.get('opportunity_ranking_6') or {}).get('top_candidates') or []; ranked += [x for x in extra if isinstance(x,dict) and symbol(x.get('symbol'))]
    evaluated=[]; seen=set(); now=datetime.now(timezone.utc)
    for raw in ranked:
        s=symbol(raw.get('symbol')); cat=category(raw); key=candidate_key(raw)
        if key in seen:continue
        seen.add(key); base=num(raw.get('ranker_score') or raw.get('score')); score=base; reasons=[]; blocked=False; count=counts.get(s,0); follow=material_followup(raw)
        if base<MIN_SCORE:continue
        if not news_supported(raw):blocked=True;reasons.append('news_asset_not_explicitly_supported')
        # Publication history is now status-aware. The old guard only counted
        # PUBLISHED_AUTONOMOUSLY, so verified API publications became invisible
        # and the same asset could be selected again immediately.
        last_same=[r for r in recent if symbol(r.get('symbol') or r.get('selected_lane_symbol'))==s]
        within_window=False
        for r in last_same:
            t=parse_time(r)
            if t and now-t<=timedelta(hours=SAME_ASSET_HOURS):within_window=True;break
        if within_window and not follow:blocked=True;reasons.append('same_asset_recently_published')
        if s=='BTC' and count>=BTC_MAX_RECENT and not follow:blocked=True;reasons.append(f'btc_overexposed_{count}_recent_posts')
        elif count>=ASSET_MAX_RECENT and not follow:blocked=True;reasons.append(f'asset_overexposed_{count}_recent_posts')
        same_cat=sum(1 for r in recent[-5:] if category(r)==cat)
        if same_cat>=2 and cat not in {'creator_signal_outcome','follow_up'}:score-=6;reasons.append('category_repeat_penalty')
        sim=max((similarity(text_of(raw),text_of(r)) for r in recent_texts),default=0.0)
        if sim>=SIMILARITY_BLOCK and not follow:blocked=True;reasons.append(f'semantic_similarity_{sim:.2f}')
        if count==0:score+=7;reasons.append('new_asset_bonus')
        if lane_priority(cat)==2:score+=8;reasons.append('primary_signal_lane_bonus')
        if cat in {'next_gainer_candidate','next_loser_candidate'}:score+=3;reasons.append('early_mover_discovery_bonus')
        evaluated.append({'candidate':raw,'score_before_guard':round(base,2),'portfolio_score':round(score,2),'lane_priority':lane_priority(cat),'asset_recent_count':count,'recent_same_category':same_cat,'max_recent_semantic_similarity':round(sim,3),'hard_block':blocked,'reasons':reasons})
    allowed=[x for x in evaluated if not x['hard_block']]; allowed.sort(key=lambda x:(x['lane_priority'],x['portfolio_score']),reverse=True); chosen_entry=allowed[0] if allowed else None; chosen=chosen_entry['candidate'] if chosen_entry else None
    if current and material_followup(current):chosen=current; decision='PROTECTED_OUTCOME_OR_FOLLOWUP'; reason='material_outcome_update_is_allowed_to_revisit_a_recent_asset'; chosen_entry=None
    elif chosen:decision='DIVERSIFIED_STORY_SELECTED';reason='portfolio_manager_selected_the_best_non_repetitive_candidate'
    else:decision='WAIT_FOR_DIFFERENT_STORY';reason='all_qualified_candidates_are_repetitive_or_unsupported'
    publish=chosen is not None
    if publish:
        chosen=dict(chosen);chosen['portfolio_guard_selected']=True;chosen['portfolio_score']=round(chosen_entry['portfolio_score'],2) if chosen_entry else num(chosen.get('score'));chosen['symbol']=symbol(chosen.get('symbol'))+'USDT';pre['selected_opportunity']=chosen;brief['authoritative_selection']=chosen;brief['portfolio_guard']={'decision':decision,'reason':reason,'selected_symbol':symbol(chosen.get('symbol')),'selected_category':category(chosen),'recent_asset_counts':counts,'recent_window':len(recent)};PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8');DIRECTOR.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    else:pre['selected_opportunity']={};PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'version':'1.3-publication-truth-dedupe','publish':publish,'decision':decision,'reason':reason,'selected':chosen,'recent_asset_counts':counts,'recent_window':len(recent),'candidates_considered':len(evaluated),'blocked_candidates':[x for x in evaluated if x['hard_block']][:20],'top_allowed_candidates':allowed[:12],'policy':{'btc_max_recent_posts':BTC_MAX_RECENT,'asset_max_recent_posts':ASSET_MAX_RECENT,'same_asset_cooldown_hours':SAME_ASSET_HOURS,'publication_statuses_counted':sorted(accepted) if 'accepted' in locals() else ['PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','PUBLISHED_SUBMITTED_504','VERIFIED_PUBLISHED'],'semantic_similarity_block':SIMILARITY_BLOCK,'generic_news_cannot_create_btc_fallback':True,'wait_when_repetitive':True,'outcome_followups_can_revisit_asset':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())