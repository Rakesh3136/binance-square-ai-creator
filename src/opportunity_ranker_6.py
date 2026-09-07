"""Creator 6.3 + 22.1 evidence-weighted opportunity ranking authority.

Adds a bounded audience-learning adjustment from Creator 22.0. Historical
performance is observational only: it can increase/decrease testing priority,
but it cannot establish causality, invent metrics, or override hard editorial
and publication safety rules.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRIEF=ROOT/'data/live/content_director_brief.json'
INTEL=ROOT/'data/live/market_intelligence_6.json'
PREF=ROOT/'data/live/editorial_preflight.json'
AUDIENCE=ROOT/'data/live/creator_22_0_audience_board.json'
OUT=ROOT/'data/live/opportunity_ranking_6.json'


def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def num(x):
    try:return float(x)
    except Exception:return 0.0

def sym(x):
    return str(x or '').upper().replace('$','').replace('USDT','').strip()

def score_story(s,intel):
    lane=str(s.get('lane') or '').lower()
    score=num(s.get('score'))
    move=abs(num(s.get('price_change_percent')))
    vol=num(s.get('quote_volume_usdt'))
    rng=num(s.get('intraday_range_percent'))
    signal=num(s.get('content_signal_score'))
    score += min(10.0, move*.15) + min(8.0, rng*.10) + min(8.0, signal*.08)
    if vol >= 1e8: score += 4
    if s.get('has_1h_ohlcv'): score += 3
    if lane in {'creator_signal_outcome','follow_up'}: score += 5
    for d in intel.get('derivatives') or []:
        if sym(d.get('symbol')) != sym(s.get('symbol')): continue
        fr=abs(num(d.get('last_funding_rate'))); oi=abs(num(d.get('open_interest_change_1h_pct')))
        if fr >= .001: score += 3
        if fr >= .003: score += 3
        if oi >= 3: score += 3
        if oi >= 8: score += 3
        break
    for b in intel.get('orderbook_imbalance') or []:
        if sym(b.get('symbol')) == sym(s.get('symbol')) and abs(num(b.get('orderbook_imbalance_pct'))) >= 25:
            score += 2
            break
    return round(score,2)

def news_relevance(s):
    title=str(s.get('title') or '').lower(); symbols=s.get('symbols') or []
    crypto_terms=('bitcoin','btc','ethereum','eth','crypto','blockchain','binance','solana','sol','defi','stablecoin','token','web3','altcoin','xrp','dogecoin','etf','digital asset','on-chain')
    direct=sum(1 for k in crypto_terms if k in title)
    asset_bonus=8 if symbols else 0
    generic_macro=('fed','federal reserve','inflation','rates','treasury','dollar','gold','silver')
    generic=sum(1 for k in generic_macro if k in title)
    return direct*4+asset_bonus-generic*2

def audience_adjustment(candidate, board):
    """Return a small observational preference, never a causal verdict."""
    patterns=board.get('observed_patterns') or []
    if not patterns:
        return 0.0, 'No audience-learning adjustment available.'
    cat=str(candidate.get('category') or candidate.get('lane') or '').lower()
    fmt=str(candidate.get('format') or '').lower()
    symbol=sym(candidate.get('symbol'))
    scores=[]
    for item in patterns:
        if num(item.get('samples')) < 3:
            continue
        dims=item.get('dimensions') or {}
        dcat=str(dims.get('category') or '').lower()
        dfmt=str(dims.get('format') or '').lower()
        dsym=sym(dims.get('symbol'))
        match=False
        if cat and dcat not in {'','unknown'} and cat == dcat: match=True
        if fmt and dfmt not in {'','unknown'} and fmt == dfmt: match=True
        if symbol and dsym and symbol == dsym: match=True
        if not match: continue
        views=num(item.get('avg_views'))
        replies=num(item.get('avg_replies'))
        followers=num(item.get('avg_followers_gained'))
        scores.append((views, replies, followers, item))
    if not scores:
        return 0.0, 'No repeated audience pattern matched this opportunity.'
    # Use rank position rather than raw scale so one viral outlier cannot dominate.
    scores.sort(key=lambda x:(x[0],x[1],x[2]), reverse=True)
    best=scores[0][3]
    if scores[0][0] > 0:
        adjustment=6.0
    elif scores[0][1] > 0 or scores[0][2] > 0:
        adjustment=3.0
    else:
        adjustment=-3.0
    return adjustment, 'Repeated observed audience pattern matched; adjustment is preference-only, not causal.'

def main():
    brief=load(BRIEF);intel=load(INTEL);pref=load(PREF);audience=load(AUDIENCE)
    ranked=[]
    for raw in brief.get('ranked_stories') or []:
        if not isinstance(raw,dict):continue
        s=dict(raw)
        if s.get('title'):
            relevance=news_relevance(s)
            s['ranker_score']=round(num(s.get('score'))+relevance,2)
            s['chartable']=bool(s.get('symbols'))
            if not s['chartable']:
                s['ranker_score']=round(s['ranker_score']-40,2)
                s['ranker_note']='No evidence-backed asset symbol; not eligible as primary TradingView story.'
            if relevance < 0 and not s.get('symbols'):
                s['ranker_score']=round(s['ranker_score']-5,2)
        else:
            s['ranker_score']=score_story(s,intel)
            s['chartable']=bool(s.get('symbol'))
        adj,note=audience_adjustment(s,audience)
        s['audience_learning_adjustment']=adj
        s['audience_learning_note']=note
        s['ranker_score']=round(num(s.get('ranker_score'))+adj,2)
        ranked.append(s)
    ranked.sort(key=lambda x:num(x.get('ranker_score')),reverse=True)
    chosen=ranked[0] if ranked else {}
    current=pref.get('selected_opportunity') or {}
    current_category=str(current.get('category') or '').lower()
    manual=bool(pref.get('manual_topic')) or bool(current.get('manual_topic'))
    protected=current_category in {'creator_signal_outcome','follow_up'}
    if manual or protected:
        chosen=current
        reason='Protected manual/verified editorial selection retained.'
    else:
        reason='Creator 6.3 evidence ranker + bounded Creator 22.1 audience preference selected the strongest eligible opportunity.'
        selected=dict(current)
        if chosen.get('title'):
            symbols=chosen.get('symbols') or []
            if not symbols:
                alternatives=[x for x in ranked[1:] if x.get('symbols')]
                if alternatives: chosen=dict(alternatives[0])
                else: raise SystemExit('No chartable news/market opportunity available for TradingView-only publication policy')
            selected.update({'category':'breaking_news' if num(chosen.get('score'))>=70 else 'news_and_macro','news_title':chosen.get('title'),'news_url':chosen.get('url'),'news_source':chosen.get('source'),'news_published_at':chosen.get('published_at'),'news_score':num(chosen.get('score')),'symbol':sym((chosen.get('symbols') or [])[0]),'reason':reason,'ranker_score':num(chosen.get('ranker_score')),'audience_learning_adjustment':num(chosen.get('audience_learning_adjustment')),'audience_learning_note':chosen.get('audience_learning_note')})
        else:
            selected.update({'category':chosen.get('lane') or current.get('category') or 'top_mover','symbol':sym(chosen.get('symbol') or current.get('symbol')),'reason':reason,'ranker_score':num(chosen.get('ranker_score')),'audience_learning_adjustment':num(chosen.get('audience_learning_adjustment')),'audience_learning_note':chosen.get('audience_learning_note')})
        chosen=selected
    if not chosen.get('symbol'):
        raise SystemExit('Selected opportunity has no evidence-backed chart asset')
    pref['selected_opportunity']=chosen
    pref['opportunity_ranking_6']={'version':'6.3+22.1','generated_at':datetime.now(timezone.utc).isoformat(),'selection_reason':reason,'manual_or_protected':manual or protected,'audience_learning_used':bool(audience.get('observed_patterns')),'top_candidates':ranked[:15]}
    pref['content_director_instruction']='Creator 6.3 ranker + Creator 22.1 bounded audience learning is authoritative. Use the selected opportunity exactly; do not substitute another asset or story. Never use BTC as an arbitrary news-chart proxy.'
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'version':'6.3+22.1','generated_at':datetime.now(timezone.utc).isoformat(),'selected':chosen,'top_candidates':ranked[:25],'audience_learning':{'used':bool(audience.get('observed_patterns')),'source':'creator_22_0_audience_board.json','causal_claims_allowed':False,'max_adjustment':6.0},'policy':['Market/news candidates compete on one score.','Audience learning only changes bounded testing preference from repeated explicit performance.','Audience observations never establish causality.','News without an evidence-backed asset symbol cannot become the primary TradingView story.','Funding/OI/orderbook observations confirm rather than independently create a story.','Manual topics and verified creator outcomes/follow-ups remain protected.','No missing evidence is invented.']},indent=2,ensure_ascii=False),encoding='utf-8')
    PREF.write_text(json.dumps(pref,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'6.3+22.1','selected_category':chosen.get('category'),'selected_symbol':chosen.get('symbol'),'selected_news':chosen.get('news_title'),'ranked_candidates':len(ranked),'ranker_score':chosen.get('ranker_score'),'audience_learning_used':bool(audience.get('observed_patterns'))},indent=2))

if __name__=='__main__':main()
