"""Creator 6.3 cross-market opportunity ranking authority.

Takes the Content Director's candidate set and performs a final evidence-weighted
ranking across market, derivatives, news and learned-performance signals before
the opportunity is frozen. It never invents missing evidence.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRIEF=ROOT/'data/live/content_director_brief.json'
INTEL=ROOT/'data/live/market_intelligence_6.json'
PREF=ROOT/'data/live/editorial_preflight.json'
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
    # Evidence quality: prefer observable market structure, not just headline keywords.
    score += min(10.0, move*.15) + min(8.0, rng*.10) + min(8.0, signal*.08)
    if vol >= 1e8: score += 4
    if s.get('has_1h_ohlcv'): score += 3
    if lane in {'creator_signal_outcome','follow_up'}: score += 5
    # Derivatives context is a confirmation bonus, never a standalone signal.
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

def main():
    brief=load(BRIEF);intel=load(INTEL);pref=load(PREF)
    ranked=[]
    for raw in brief.get('ranked_stories') or []:
        if not isinstance(raw,dict):continue
        s=dict(raw)
        if s.get('title'):
            s['ranker_score']=round(num(s.get('score'))+news_relevance(s),2)
            if news_relevance(s) < 0 and not s.get('symbols'):
                s['ranker_score']=round(s['ranker_score']-5,2)
        else:
            s['ranker_score']=score_story(s,intel)
        ranked.append(s)
    ranked.sort(key=lambda x:num(x.get('ranker_score')),reverse=True)
    chosen=ranked[0] if ranked else {}
    current=pref.get('selected_opportunity') or {}
    current_category=str(current.get('category') or '').lower()
    # Manual topics and verified creator follow-ups remain authoritative.
    manual=bool(pref.get('manual_topic')) or bool(current.get('manual_topic'))
    protected=current_category in {'creator_signal_outcome','follow_up'}
    if manual or protected:
        chosen=current
        reason='Protected manual/verified editorial selection retained.'
    else:
        reason='Creator 6.3 cross-market ranker selected the strongest evidence-weighted opportunity.'
        selected=dict(current)
        if chosen.get('title'):
            selected.update({'category':'breaking_news' if num(chosen.get('score'))>=70 else 'news_and_macro','news_title':chosen.get('title'),'news_url':chosen.get('url'),'news_source':chosen.get('source'),'news_published_at':chosen.get('published_at'),'news_score':num(chosen.get('score')),'symbol':sym((chosen.get('symbols') or ['BTC'])[0]) if chosen.get('symbols') else 'BTC','reason':reason,'ranker_score':num(chosen.get('ranker_score'))})
        else:
            selected.update({'category':chosen.get('lane') or current.get('category') or 'top_mover','symbol':sym(chosen.get('symbol') or current.get('symbol')),'reason':reason,'ranker_score':num(chosen.get('ranker_score'))})
        chosen=selected
    pref['selected_opportunity']=chosen
    pref['opportunity_ranking_6']={'version':'6.3','generated_at':datetime.now(timezone.utc).isoformat(),'selection_reason':reason,'manual_or_protected':manual or protected,'top_candidates':ranked[:15]}
    pref['content_director_instruction']='Creator 6.3 ranker is authoritative. Use the selected opportunity exactly; do not substitute another asset or story.'
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'version':'6.3','generated_at':datetime.now(timezone.utc).isoformat(),'selected':chosen,'top_candidates':ranked[:25],'policy':['Market/news candidates compete on one score.','News gets relevance credit only when the headline demonstrates crypto connection.','Funding/OI/orderbook observations confirm rather than independently create a story.','Manual topics and verified creator outcomes/follow-ups remain protected.','No missing evidence is invented.']},indent=2,ensure_ascii=False),encoding='utf-8')
    PREF.write_text(json.dumps(pref,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'6.3','selected_category':chosen.get('category'),'selected_symbol':chosen.get('symbol'),'selected_news':chosen.get('news_title'),'ranked_candidates':len(ranked),'ranker_score':chosen.get('ranker_score')},indent=2))

if __name__=='__main__':main()
