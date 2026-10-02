"""NIC portfolio/editorial memory guard.

This is the authoritative anti-repetition selector. It runs inside the existing
cadence step, so a WAIT here makes autonomous_cadence_6 publish=false before any
writer/provider is invoked. It is intentionally provider-neutral.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; DIRECTOR=ROOT/'data/live/content_director_brief.json'; QUEUE=ROOT/'data/live/discovery_queue.json'; LOG=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/content_portfolio_guard.json'
MIN_SCORE=float(os.getenv('PORTFOLIO_MIN_SCORE','68')); KNOWLEDGE_MIN_SCORE=float(os.getenv('PORTFOLIO_KNOWLEDGE_MIN_SCORE','62')); RECENT_WINDOW=int(os.getenv('PORTFOLIO_RECENT_WINDOW','40')); BTC_MAX_RECENT=int(os.getenv('PORTFOLIO_BTC_MAX_RECENT','3')); ASSET_MAX_RECENT=int(os.getenv('PORTFOLIO_ASSET_MAX_RECENT','2')); SIMILARITY_BLOCK=float(os.getenv('PORTFOLIO_SIMILARITY_BLOCK','0.58')); SAME_ASSET_HOURS=float(os.getenv('PORTFOLIO_SAME_ASSET_HOURS','12')); SAME_CATEGORY_HOURS=float(os.getenv('PORTFOLIO_SAME_CATEGORY_HOURS','6')); SIGNAL_ASSET_24H_MAX=int(os.getenv('PORTFOLIO_SIGNAL_ASSET_24H_MAX','1'))
PRIMARY={'creator_signal_outcome','capital_flow_long','capital_flow_short','follow_up','technical_setup','top_gainers','top_losers','high_volatility','volume_leaders','next_gainer_candidate','next_loser_candidate','market_setup','momentum'}
KNOWLEDGE={'education','research_insight','market_mechanism','data_surprise','watchlist','comparison'}
FOLLOW_UP={'creator_signal_outcome','follow_up','outcome_accountability','breaking_news','news_market_impact','news_and_macro','research_lesson'}
STOPWORDS={'the','a','an','and','or','to','of','for','in','on','with','from','as','is','are','this','that','it','its','at','by','be','has','have','will','can','now','why','what','how','than','into','after','over','under','market','crypto','price','today','latest','update','binance'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def num(v,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d
def symbol(v):return str(v or '').upper().replace('BINANCE:','').replace('$','').strip().removesuffix('USDT')
def category(item):return str(item.get('category') or item.get('lane') or item.get('content_category') or item.get('type') or '').lower() if isinstance(item,dict) else ''
def words(text):return {x for x in re.findall(r'[a-z0-9]{3,}',str(text or '').lower()) if x not in STOPWORDS}
def similarity(a,b):
    x,y=words(a),words(b); return len(x&y)/max(1,len(x|y)) if x and y else 0.0
def text_of(item):
    if not isinstance(item,dict):return ''
    setup=item.get('trade_setup') or {}; setup=setup if isinstance(setup,dict) else {}
    evidence=item.get('evidence'); evidence=json.dumps(evidence,ensure_ascii=False) if isinstance(evidence,(list,dict)) else evidence
    return ' '.join(str(x or '') for x in [item.get('topic'),item.get('title'),item.get('news_title'),item.get('hook'),item.get('reason'),item.get('editorial_style'),item.get('story_type'),item.get('content_intent'),setup.get('side'),setup.get('trigger'),setup.get('invalidation'),evidence])
def parse_time(row):
    try:
        dt=datetime.fromisoformat(str(row.get('published_at') or row.get('timestamp') or '').replace('Z','+00:00')); return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:return None
def recent_publications():
    if not LOG.exists():return []
    accepted={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','PUBLISHED_SUBMITTED_504','VERIFIED_PUBLISHED'}; rows=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-300:]:
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict) and str(r.get('status') or '') in accepted: rows.append(r)
    return rows[-RECENT_WINDOW:]
def material_followup(c):
    if not isinstance(c,dict):return False
    cat=category(c)
    if cat in {'creator_signal_outcome','follow_up','outcome_accountability'}:
        return bool(c.get('proof_status') or c.get('outcome') or c.get('outcome_status') or c.get('new_evidence') or c.get('next_hook'))
    if cat in {'breaking_news','news_market_impact','news_and_macro','research_lesson'}:
        return bool(c.get('news_title') or c.get('new_evidence') or c.get('catalyst') or c.get('event_id') or c.get('news_event_id'))
    return bool(c.get('new_evidence') or c.get('catalyst') or c.get('event_id') or c.get('news_event_id'))
def candidate_key(c):return f'{symbol(c.get("symbol"))}|{category(c)}|{str(c.get("type") or "").lower()}|{str(c.get("content_intent") or "").lower()}' if isinstance(c,dict) else ''
def news_supported(c):
    if not isinstance(c,dict):return False
    if category(c) not in {'breaking_news','news_and_macro','news_market_impact','news'}:return True
    s=symbol(c.get('symbol')).lower(); blob=(str(c.get('title') or '')+' '+str(c.get('news_title') or '')+' '+str(c.get('summary') or '')).lower()
    return bool(s) and bool(re.search(r'(?<![a-z0-9])(?:\$?'+re.escape(s)+r')(?![a-z0-9])',blob))
def main():
    pre=load(PREFLIGHT); brief=load(DIRECTOR); queue_state=load(QUEUE); current=pre.get('selected_opportunity') or {}; current=current if isinstance(current,dict) else {}; recent=recent_publications(); now=datetime.now(timezone.utc)
    counts={}
    for r in recent:
        s=symbol(r.get('symbol') or r.get('selected_lane_symbol'))
        if s:counts[s]=counts.get(s,0)+1
    recent_texts=[text_of(r) for r in recent[-12:]]
    ranked=[]
    for item in (queue_state.get('candidates') or []):
        if not isinstance(item,dict):continue
        candidate=item.get('candidate') if isinstance(item.get('candidate'),dict) else item
        if isinstance(candidate,dict):ranked.append(candidate)
    ranked += [x for x in (brief.get('ranked_stories') or []) if isinstance(x,dict)]
    ranked += [x for x in ((pre.get('opportunity_ranking_6') or {}).get('top_candidates') or []) if isinstance(x,dict)]
    if current:ranked.insert(0,current)
    evaluated=[];seen=set()
    for raw in ranked:
        s=symbol(raw.get('symbol')); cat=category(raw); key=candidate_key(raw); knowledge=cat in KNOWLEDGE
        if (not s and not knowledge) or key in seen:continue
        seen.add(key); base=num(raw.get('ranker_score') or raw.get('score') or raw.get('adjusted_score')); floor=KNOWLEDGE_MIN_SCORE if knowledge else MIN_SCORE
        if base<floor:continue
        score=base; reasons=[]; blocked=False; count=counts.get(s,0); follow=material_followup(raw)
        if knowledge:
            research=raw.get('research') if isinstance(raw.get('research'),dict) else {}; evidence=max(num(raw.get('evidence_score')),num(research.get('evidence_score')),num(research.get('information_advantage_score'))*.7+num(research.get('undercoverage_score'))*.3)
            if evidence<62:blocked=True;reasons.append(f'knowledge_evidence_too_weak_{evidence:.1f}')
        if not news_supported(raw):blocked=True;reasons.append('news_asset_not_explicitly_supported')
        last_same=[r for r in recent if s and symbol(r.get('symbol') or r.get('selected_lane_symbol'))==s]
        newest=None; same_cat_recent=False; same_asset_24=0
        for r in last_same:
            t=parse_time(r)
            if not t:continue
            age=now-t
            if age<=timedelta(hours=24):same_asset_24+=1
            if newest is None or age<newest:newest=age
            if age<=timedelta(hours=SAME_CATEGORY_HOURS) and category(r)==cat:same_cat_recent=True
        # NIC 19: the same asset is not a new story merely because its price
        # changed. Re-open it only for an explicit outcome/follow-up/new event.
        if newest is not None and newest<=timedelta(hours=SAME_ASSET_HOURS) and not follow:
            blocked=True;reasons.append(f'nic19_same_asset_cooldown_{newest.total_seconds()/3600:.2f}h')
        if cat in PRIMARY and same_asset_24>=SIGNAL_ASSET_24H_MAX and not follow:
            blocked=True;reasons.append(f'nic19_repeated_signal_asset_{same_asset_24}_in_24h')
        if same_cat_recent and not follow:
            blocked=True;reasons.append('same_category_cooldown')
        if s=='BTC' and count>=BTC_MAX_RECENT and not follow:blocked=True;reasons.append(f'btc_overexposed_{count}_recent_posts')
        elif s and count>=ASSET_MAX_RECENT and not follow:blocked=True;reasons.append(f'asset_overexposed_{count}_recent_posts')
        same_cat=sum(1 for r in recent[-8:] if category(r)==cat)
        if same_cat and cat not in {'creator_signal_outcome','follow_up'}:score-=6;reasons.append('category_repeat_penalty')
        recent_categories={category(r) for r in recent[-6:]}
        if cat not in recent_categories:score+=8;reasons.append('lane_diversity_bonus')
        sim=max((similarity(text_of(raw),text_of(r)) for r in recent_texts),default=0.0)
        if sim>=SIMILARITY_BLOCK and not follow:blocked=True;reasons.append(f'semantic_similarity_{sim:.2f}')
        if count==0:score+=7;reasons.append('new_asset_bonus')
        if cat in PRIMARY:score+=8;reasons.append('primary_signal_lane_bonus')
        evaluated.append({'candidate':raw,'score_before_guard':round(base,2),'portfolio_score':round(score,2),'asset_recent_count':count,'asset_24h_count':same_asset_24,'hours_since_latest':None if newest is None else round(newest.total_seconds()/3600,2),'hard_block':blocked,'reasons':reasons})
    allowed=[x for x in evaluated if not x['hard_block']]; allowed.sort(key=lambda x:x['portfolio_score'],reverse=True)
    chosen_entry=allowed[0] if allowed else None; chosen=chosen_entry['candidate'] if chosen_entry else None
    if chosen:
        decision='DIVERSIFIED_STORY_SELECTED';reason='NIC19 selected a non-repetitive opportunity';publish=True
    else:
        decision='WAIT_FOR_DIFFERENT_STORY';reason='NIC19 found no sufficiently new story';publish=False
    # A manual topic is still allowed, but it must pass the downstream quality gates.
    if pre.get('manual_topic') and current:
        chosen=current; publish=True; decision='MANUAL_TOPIC'; reason='explicit manual topic'; chosen_entry=None
    if publish:
        chosen=dict(chosen);chosen['portfolio_guard_selected']=True;chosen['portfolio_score']=round(chosen_entry['portfolio_score'],2) if chosen_entry else num(chosen.get('score'));pre['selected_opportunity']=chosen;brief['authoritative_selection']=chosen;brief['portfolio_guard']={'decision':decision,'reason':reason,'selected_symbol':symbol(chosen.get('symbol')),'selected_category':category(chosen),'recent_asset_counts':counts,'recent_window':len(recent),'nic19':True}
        PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8');DIRECTOR.write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    else:
        pre['selected_opportunity']={}; pre['nic19_wait']={'reason':reason,'generated_at':now.isoformat()}; PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'generated_at':now.isoformat(),'version':'19.1-editorial-memory','publish':publish,'decision':decision,'reason':reason,'selected':chosen,'recent_asset_counts':counts,'recent_window':len(recent),'candidates_considered':len(evaluated),'blocked_candidates':[x for x in evaluated if x['hard_block']][:25],'top_allowed_candidates':allowed[:12],'policy':{'same_asset_cooldown_hours':SAME_ASSET_HOURS,'signal_asset_24h_max':SIGNAL_ASSET_24H_MAX,'same_category_cooldown_hours':SAME_CATEGORY_HOURS,'semantic_similarity_block':SIMILARITY_BLOCK,'provider_independent':True,'wait_when_repetitive':True,'followups_and_new_events_allowed':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())