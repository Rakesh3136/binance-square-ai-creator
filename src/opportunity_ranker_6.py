"""Creator 6.4 evidence-weighted opportunity ranking authority.

Adds a bounded early-mover discovery lane: assets showing early acceleration,
participation and confirmation signals can be selected before they become top
gainers/losers. This is a conditional discovery system, never a guarantee or
market-manipulation mechanism.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BRIEF=ROOT/'data/live/content_director_brief.json'
INTEL=ROOT/'data/live/market_intelligence_6.json'
MARKET=ROOT/'data/live/market_snapshot.json'
PREF=ROOT/'data/live/editorial_preflight.json'
AUDIENCE=ROOT/'data/live/creator_22_0_audience_board.json'
PROOF=ROOT/'data/live/public_prediction_proof.json'
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
    lane=str(s.get('lane') or '').lower();score=num(s.get('score'));move=abs(num(s.get('price_change_percent')));vol=num(s.get('quote_volume_usdt'));rng=num(s.get('intraday_range_percent'));signal=num(s.get('content_signal_score'))
    score += min(10.0,move*.15)+min(8.0,rng*.10)+min(8.0,signal*.08)
    if vol >= 1e8: score += 4
    if s.get('has_1h_ohlcv'): score += 3
    if lane in {'creator_signal_outcome','follow_up'}: score += 5
    for d in intel.get('derivatives') or []:
        if sym(d.get('symbol')) != sym(s.get('symbol')): continue
        fr=abs(num(d.get('last_funding_rate')));oi=abs(num(d.get('open_interest_change_1h_pct')))
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

def early_mover_candidates(market,intel):
    """Find plausible next gainers/losers before they dominate the leaderboard."""
    pools=[]
    for key in ('top_content_signals','highest_volume','top_gainers','top_losers'):
        pools.extend(x for x in (market.get(key) or []) if isinstance(x,dict) and x.get('symbol'))
    seen=set();out=[]
    for x in pools:
        s=sym(x.get('symbol'))
        if not s or s in seen or s in {'BTC','ETH'}: continue
        seen.add(s)
        move=num(x.get('price_change_percent'));rng=num(x.get('intraday_range_percent'));signal=num(x.get('content_signal_score'));vol=num(x.get('quote_volume_usdt') or x.get('quote_volume'))
        if abs(move) < 0.8 or abs(move) > 15: continue
        # Early-mover score rewards participation/acceleration but discounts a move
        # that has already become an extreme leaderboard event.
        score=35 + min(24,abs(move)*2.0) + min(15,rng*1.2) + min(15,signal*.15)
        if vol >= 1e7: score += 4
        if vol >= 1e8: score += 4
        evidence=[]
        for d in intel.get('derivatives') or []:
            if sym(d.get('symbol')) != s: continue
            oi=num(d.get('open_interest_change_1h_pct'));fr=abs(num(d.get('last_funding_rate')))
            if oi >= 3: score += min(8,oi*.5); evidence.append(f'oi_1h={oi:.2f}%')
            if fr >= .001: score += 3; evidence.append(f'funding={fr:.5f}')
            if fr >= .003: score += 3; evidence.append('elevated_funding')
            break
        for b in intel.get('orderbook_imbalance') or []:
            if sym(b.get('symbol')) == s:
                imb=num(b.get('orderbook_imbalance_pct'))
                if abs(imb)>=20: score += 3; evidence.append(f'orderbook={imb:.1f}%')
                break
        if score < 65: continue
        direction='next_gainer_candidate' if move > 0 else 'next_loser_candidate'
        out.append({'category':direction,'lane':direction,'symbol':s,'score':round(min(100,score),2),'ranker_score':round(min(100,score),2),'price_change_percent':move,'directional_move':move,'intraday_range_percent':rng,'quote_volume_usdt':vol,'content_signal_score':signal,'reason':'early participation and price-structure acceleration; candidate requires confirmation','early_mover':True,'confirmation_required':True,'evidence':evidence,'has_1h_ohlcv':bool(x.get('candles_1h') or x.get('ohlcv_1h')),'chartable':True})
    out.sort(key=lambda x:x['ranker_score'],reverse=True)
    return out[:12]

def news_relevance(s):
    title=str(s.get('title') or '').lower(); symbols=s.get('symbols') or []
    crypto_terms=('bitcoin','btc','ethereum','eth','crypto','blockchain','binance','solana','sol','defi','stablecoin','token','web3','altcoin','xrp','dogecoin','etf','digital asset','on-chain')
    direct=sum(1 for k in crypto_terms if k in title);asset_bonus=8 if symbols else 0
    generic_macro=('fed','federal reserve','inflation','rates','treasury','dollar','gold','silver');generic=sum(1 for k in generic_macro if k in title)
    return direct*4+asset_bonus-generic*2

def audience_adjustment(candidate,board):
    patterns=board.get('observed_patterns') or []
    if not patterns:return 0.0,'No audience-learning adjustment available.'
    cat=str(candidate.get('category') or candidate.get('lane') or '').lower();fmt=str(candidate.get('format') or '').lower();symbol=sym(candidate.get('symbol'));scores=[]
    for item in patterns:
        if num(item.get('samples')) < 3:continue
        dims=item.get('dimensions') or {};dcat=str(dims.get('category') or '').lower();dfmt=str(dims.get('format') or '').lower();dsym=sym(dims.get('symbol'));match=False
        if cat and dcat not in {'','unknown'} and cat == dcat:match=True
        if fmt and dfmt not in {'','unknown'} and fmt == dfmt:match=True
        if symbol and dsym and symbol == dsym:match=True
        if not match:continue
        scores.append((num(item.get('avg_views')),num(item.get('avg_replies')),num(item.get('avg_followers_gained')),item))
    if not scores:return 0.0,'No repeated audience pattern matched this opportunity.'
    scores.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True);best=scores[0][3]
    adjustment=6.0 if scores[0][0] > 0 else (3.0 if scores[0][1] > 0 or scores[0][2] > 0 else -3.0)
    return adjustment,'Repeated observed audience pattern matched; adjustment is preference-only, not causal.'

def proof_selection(proof):
    if proof.get('status') != 'VERIFIED_WIN_AVAILABLE' or not proof.get('publishable'):return {}
    symbol=sym(proof.get('symbol'))
    if not symbol:return {}
    return {'category':'creator_signal_outcome','lane':'accountability','symbol':symbol,'score':100.0,'ranker_score':100.0,'reason':'Verified prior prediction outcome is available for transparent public proof.','proof_status':proof.get('status'),'proof_type':proof.get('proof_type'),'call_id':proof.get('call_id'),'post_id':proof.get('post_id'),'direction':proof.get('direction'),'reference_price':proof.get('reference_price'),'target':proof.get('target'),'evaluated_at':proof.get('evaluated_at'),'original_publication_found':bool(proof.get('original_publication_found')),'content_brief':proof.get('content_brief'),'next_hook':proof.get('next_hook'),'chartable':True}

def main():
    brief=load(BRIEF);intel=load(INTEL);market=load(MARKET);pref=load(PREF);audience=load(AUDIENCE);proof=load(PROOF)
    proof_choice=proof_selection(proof);ranked=[]
    for raw in brief.get('ranked_stories') or []:
        if not isinstance(raw,dict):continue
        s=dict(raw)
        if s.get('title'):
            relevance=news_relevance(s);s['ranker_score']=round(num(s.get('score'))+relevance,2);s['chartable']=bool(s.get('symbols'))
            if not s['chartable']:s['ranker_score']=round(s['ranker_score']-40,2);s['ranker_note']='No evidence-backed asset symbol; not eligible as primary TradingView story.'
            if relevance < 0 and not s.get('symbols'):s['ranker_score']=round(s['ranker_score']-5,2)
        else:
            s['ranker_score']=score_story(s,intel);s['chartable']=bool(s.get('symbol'))
        adj,note=audience_adjustment(s,audience);s['audience_learning_adjustment']=adj;s['audience_learning_note']=note;s['ranker_score']=round(num(s.get('ranker_score'))+adj,2);ranked.append(s)
    early=early_mover_candidates(market,intel)
    for candidate in early:
        adj,note=audience_adjustment(candidate,audience);candidate['audience_learning_adjustment']=adj;candidate['audience_learning_note']=note;candidate['ranker_score']=round(min(100,num(candidate['ranker_score'])+adj),2);ranked.append(candidate)
    if proof_choice:ranked.insert(0,proof_choice)
    ranked.sort(key=lambda x:num(x.get('ranker_score')),reverse=True)
    chosen=ranked[0] if ranked else {};current=pref.get('selected_opportunity') or {};current_category=str(current.get('category') or '').lower();manual=bool(pref.get('manual_topic')) or bool(current.get('manual_topic'));protected=current_category in {'creator_signal_outcome','follow_up'}
    if proof_choice:
        chosen=proof_choice;reason='Verified prediction proof is authoritative for this cycle; show the original call and fresh evidence before introducing the next setup.';manual_or_protected=True
    elif manual or protected:
        chosen=current;reason='Protected manual/verified editorial selection retained.';manual_or_protected=True
    else:
        reason='Creator 6.4 evidence ranker + early-mover discovery + bounded audience preference selected the strongest eligible opportunity.';manual_or_protected=False;selected=dict(current)
        if chosen.get('title'):
            symbols=chosen.get('symbols') or []; 
            if not symbols:
                alternatives=[x for x in ranked[1:] if x.get('symbols')]
                if alternatives:chosen=dict(alternatives[0])
                else:raise SystemExit('No chartable news/market opportunity available for TradingView-only publication policy')
            selected.update({'category':'breaking_news' if num(chosen.get('score'))>=70 else 'news_and_macro','news_title':chosen.get('title'),'news_url':chosen.get('url'),'news_source':chosen.get('source'),'news_published_at':chosen.get('published_at'),'news_score':num(chosen.get('score')),'symbol':sym((chosen.get('symbols') or [])[0]),'reason':reason,'ranker_score':num(chosen.get('ranker_score')),'audience_learning_adjustment':num(chosen.get('audience_learning_adjustment')),'audience_learning_note':chosen.get('audience_learning_note')})
        else:
            category=chosen.get('lane') or chosen.get('category') or current.get('category') or 'top_mover';selected.update({'category':category,'symbol':sym(chosen.get('symbol') or current.get('symbol')),'reason':reason,'ranker_score':num(chosen.get('ranker_score')),'audience_learning_adjustment':num(chosen.get('audience_learning_adjustment')),'audience_learning_note':chosen.get('audience_learning_note'),'early_mover':bool(chosen.get('early_mover')),'confirmation_required':bool(chosen.get('confirmation_required')),'evidence':chosen.get('evidence') or []})
        chosen=selected
    if not chosen.get('symbol'):raise SystemExit('Selected opportunity has no evidence-backed chart asset')
    pref['selected_opportunity']=chosen
    pref['opportunity_ranking_6']={'version':'6.4','generated_at':datetime.now(timezone.utc).isoformat(),'selection_reason':reason,'manual_or_protected':manual_or_protected,'audience_learning_used':bool(audience.get('observed_patterns')),'proof_priority_used':bool(proof_choice),'early_mover_discovery_used':bool(early),'early_mover_candidates':early[:12],'top_candidates':ranked[:20]}
    pref['content_director_instruction']='Creator 6.4 ranker + early-mover discovery + bounded audience learning is authoritative. Verified prediction proof is protected when available. Early-mover candidates are conditional hypotheses: require confirmation and never promise that an asset will become a top gainer/loser. Use the selected opportunity exactly; do not substitute another asset or story. Never use BTC as an arbitrary news-chart proxy.'
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'version':'6.4','generated_at':datetime.now(timezone.utc).isoformat(),'selected':chosen,'top_candidates':ranked[:30],'early_mover_discovery':{'enabled':True,'candidates':early[:12],'method':'price acceleration + participation + range + derivatives/orderbook confirmation','guarantee':False},'audience_learning':{'used':bool(audience.get('observed_patterns')),'source':'creator_22_0_audience_board.json','causal_claims_allowed':False,'max_adjustment':6.0},'proof_priority':{'used':bool(proof_choice),'source':'public_prediction_proof.json','only_terminal_win_allowed':True},'policy':['Market/news/early-mover candidates compete on one score.','Early movers are conditional discovery candidates, not guaranteed predictions.','An early mover must have measurable participation/structure evidence and a confirmation condition.','Already-extreme moves are discounted so the lane seeks earlier opportunities rather than simply copying the current leaderboard.','Audience learning only changes bounded testing preference.','Verified prediction outcomes are published only as transparent proof when a terminal WIN exists.','News without an evidence-backed asset symbol cannot become the primary TradingView story.','No missing evidence is invented.']},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'6.4','selected_category':chosen.get('category'),'selected_symbol':chosen.get('symbol'),'selected_news':chosen.get('news_title'),'ranked_candidates':len(ranked),'ranker_score':chosen.get('ranker_score'),'early_mover_discovery_used':bool(early),'early_mover_candidates':len(early),'proof_priority_used':bool(proof_choice),'audience_learning_used':bool(audience.get('observed_patterns'))},indent=2))

if __name__=='__main__':main()
