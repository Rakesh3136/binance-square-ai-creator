from __future__ import annotations
import json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRE=ROOT/'data/live/editorial_preflight.json'
ENGAGEMENT=ROOT/'data/live/engagement_strategy.json'
MARKET=ROOT/'data/live/market_snapshot.json'
CADENCE=ROOT/'data/live/autonomous_cadence_6.json'
PORTFOLIO=ROOT/'data/live/content_portfolio_guard.json'
OUT=ROOT/'data/live/authoritative_opportunity.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com']


def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}


def symbol(v):
    if isinstance(v,dict):
        for k in ('symbol','selected_lane_symbol','topic'):
            raw=str(v.get(k) or '').upper().strip().replace('BINANCE:','')
            if raw:
                return raw if raw.endswith('USDT') else raw+'USDT'
    raw=str(v or '').upper().strip().replace('BINANCE:','')
    if not raw:
        return ''
    return raw if raw.endswith('USDT') else raw+'USDT'


def score(v):
    if not isinstance(v,dict): return 0.0
    for k in ('selected_score','effective_score','adjusted_score','portfolio_score','engagement_score','raw_score','opportunity_score','content_signal_score','news_score','score'):
        try:
            n=float(v.get(k) or 0)
            if math.isfinite(n) and n>0: return min(100.0,max(0.0,n))
        except Exception:
            pass
    return 0.0


def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'binance-square-ai-creator/4.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as h:
        return json.loads(h.read().decode('utf-8'))


def trading_symbols():
    last=None
    for base in BASES:
        try:
            data=fetch(base+'/api/v3/exchangeInfo?symbolStatus=TRADING')
            symbols={str(x.get('symbol','')).upper() for x in data.get('symbols',[]) if str(x.get('status','')).upper()=='TRADING'}
            if symbols: return symbols
        except Exception as exc:
            last=exc
    raise RuntimeError(f'Unable to verify Binance trading symbols: {last}')


def candidate_pool(portfolio, pre, engagement, market):
    """Return candidates in portfolio-authority order, then researched fallbacks.

    Crucially, a stale portfolio candidate is skipped in-place. We never use
    an old preflight BTC/news selection as a recovery path after a portfolio
    candidate has been selected and invalidated.
    """
    pool=[]
    seen=set()

    def add(x, source):
        if not isinstance(x,dict): return
        s=symbol(x)
        if not s or s in seen: return
        seen.add(s)
        item=dict(x)
        item['_freeze_source']=source
        pool.append(item)

    selected=portfolio.get('selected')
    if portfolio.get('publish') and isinstance(selected,dict):
        add(selected,'content_portfolio_guard_selected')

    for x in portfolio.get('top_allowed_candidates') or []:
        if isinstance(x,dict):
            add(x.get('candidate') if isinstance(x.get('candidate'),dict) else x,'content_portfolio_guard_ranked_fallback')

    # The portfolio guard may have rejected stale assets before freeze. Keep
    # its validated/researched ordering ahead of generic preflight choices.
    ranking=pre.get('opportunity_ranking_6') or {}
    for x in ranking.get('top_candidates') or []:
        if isinstance(x,dict): add(x,'opportunity_ranker')

    selected_pre=pre.get('selected_opportunity')
    if isinstance(selected_pre,dict): add(selected_pre,'preflight_selected_opportunity')

    for x in (engagement.get('selected'),)+(tuple(engagement.get('ranked_candidates') or [])):
        add(x,'engagement_candidate')
    for key in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        for x in market.get(key) or []:
            add(x,'market_candidate')
    return pool


def main():
    pre=load(PRE); eng=load(ENGAGEMENT); market=load(MARKET); cadence=load(CADENCE); portfolio=load(PORTFOLIO)
    valid=trading_symbols()
    pool=candidate_pool(portfolio,pre,eng,market)

    portfolio_selected=portfolio.get('selected') if isinstance(portfolio.get('selected'),dict) else {}
    portfolio_symbol=symbol(portfolio_selected)
    stale_portfolio=bool(portfolio.get('publish') and portfolio_symbol and portfolio_symbol not in valid)
    if stale_portfolio:
        print(f'Portfolio selected stale/delisted asset: {portfolio_symbol}; searching next portfolio candidate')

    chosen=None
    source=''
    for candidate in pool:
        s=symbol(candidate)
        if s not in valid:
            if s==portfolio_symbol:
                print(f'Skipping stale portfolio candidate: {s}')
            continue
        # Once a portfolio decision exists, do not let an old generic-news
        # preflight record hijack the decision. BTC is therefore not a fallback
        # merely because the portfolio asset became stale.
        chosen=candidate
        source=str(candidate.get('_freeze_source') or 'validated_candidate')
        break

    if not chosen:
        # Safe failure is intentional. A creator system with no valid,
        # non-repetitive opportunity should wait rather than manufacture BTC.
        raise SystemExit('WAIT_FOR_DIFFERENT_STORY: no currently trading portfolio/researched candidate available')

    usdt=symbol(chosen)
    if usdt not in valid:
        raise SystemExit(f'Frozen opportunity is not a currently trading Binance symbol: {usdt}')

    sym=usdt[:-4]
    chosen=dict(chosen)
    chosen.pop('_freeze_source',None)
    chosen['symbol']=usdt
    chosen_score=min(100.0,max(0.0,max(score(chosen),score(cadence))))
    if chosen_score>0: chosen['selected_score']=chosen_score
    pre['selected_opportunity']=chosen

    news_authoritative=bool(chosen.get('news_title') and (chosen.get('news_override') or chosen.get('type')=='news' or chosen.get('category') in {'breaking_news','news_and_macro','news_market_impact'}))
    frozen={
        'version':10,
        'frozen_at':datetime.now(timezone.utc).isoformat(),
        'symbol':sym,
        'symbol_usdt':usdt,
        'binance_verified':True,
        'category':chosen.get('category',''),
        'reason':chosen.get('reason',''),
        'instruction':chosen.get('instruction',''),
        'score':chosen_score,
        'raw_score':min(100.0,max(0.0,score(chosen))),
        'adjusted_score':min(100.0,max(0.0,score(chosen))),
        'engagement_score':chosen.get('engagement_score',0),
        'selected_score':chosen_score,
        'effective_score':chosen_score,
        'run_ai':bool(pre.get('run_ai',False)),
        'selection_source':source,
        'portfolio_authoritative':source.startswith('content_portfolio_guard'),
        'stale_portfolio_recovered':stale_portfolio,
        'news_authoritative':news_authoritative,
        'news_title':chosen.get('news_title',''),
        'news_source':chosen.get('news_source',chosen.get('source','')),
        'fallback_policy':'NEVER_FALLBACK_TO_BTC',
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(frozen,indent=2,ensure_ascii=False),encoding='utf-8')
    PRE.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(frozen,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
