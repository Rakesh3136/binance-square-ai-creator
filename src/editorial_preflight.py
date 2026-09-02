import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARKET = Path("data/live/market_snapshot.json")
NEWS = Path("data/live/news_snapshot.json")
MEMORY = Path("analytics/strategy_memory.json")
PUBLICATIONS = Path("analytics/publication_log.jsonl")
FEEDBACK = Path("data/live/feedback_strategy.json")
PORTFOLIO = Path("data/live/content_portfolio.json")
OUTPUT = Path("data/live/editorial_preflight.json")

MIN_MARKET_SCORE = 72.0
NEWS_FRESH_MINUTES = 180
NEWS_MATERIAL_SCORE = 55.0
MEMORY_REPEAT_PENALTY = 18.0
MEMORY_HARD_BLOCK_COUNT = 3
CATEGORY_REPEAT_PENALTY = 14.0
ASSET_COOLDOWN_HOURS = 12
LANES = ["breaking_news", "news_and_macro", "top_gainers", "top_losers", "volume_leaders", "new_listings", "high_volatility", "technical_setup", "comparison", "education"]


def load(path):
    if not path.exists(): return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def rows(value):
    return value if isinstance(value, list) else []


def extract_symbols(text):
    found=set()
    for token in re.findall(r"(?<![A-Z0-9])\$?[A-Z][A-Z0-9]{1,11}(?:USDT)?(?![A-Z0-9])", str(text or "").upper()):
        clean=token.replace("$",""); base=clean[:-4] if clean.endswith("USDT") else clean
        if 2 <= len(base) <= 10: found.add(base)
    return found


def recent_publications():
    rows_out=[]; cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    if not PUBLICATIONS.exists(): return rows_out
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row=json.loads(line)
            if not isinstance(row,dict): continue
            dt=datetime.fromisoformat(str(row.get("published_at","")).replace("Z","+00:00"))
            if dt >= cutoff:
                raw=" ".join(str(row.get(k) or "") for k in ("symbol","selected_lane_symbol","topic"))
                rows_out.append({**row,"_symbols":extract_symbols(raw),"_dt":dt})
        except Exception: pass
    return rows_out


def add_market_candidate(pool, category, item, boost=0.0):
    if not isinstance(item,dict): return
    symbol=str(item.get("symbol") or "").upper()
    if not symbol: return
    raw=float(item.get("content_signal_score") or 0)
    if category in {"top_gainers","top_losers"}:
        raw=min(100.0,abs(float(item.get("price_change_percent") or 0))*4.5+float(item.get("intraday_range_percent") or 0))
    elif category=="volume_leaders": raw=min(100.0,raw+10.0)
    elif category=="new_listings": raw=min(100.0,raw+max(0.0,25.0-float(item.get("days_since_listing") or 30)*3.0))
    pool.append({"type":"market","category":category,"topic":symbol,"raw_score":round(min(100.0,raw+boost),2),"reason":category})


def add_news_candidate(pool, article, market):
    if not isinstance(article,dict): return
    title=str(article.get("title") or "").strip()
    published=str(article.get("published_at") or "")
    try:
        dt=datetime.fromisoformat(published.replace("Z","+00:00"))
        age=(datetime.now(timezone.utc)-dt).total_seconds()/60
    except Exception:
        return
    if not title or age < -10 or age > NEWS_FRESH_MINUTES: return
    score=float(article.get("news_score") or 0)
    if score < NEWS_MATERIAL_SCORE: return
    syms=list(article.get("symbols") or [])
    if not syms: syms=list(extract_symbols(title+' '+str(article.get('summary') or '')))
    if not syms:
        # Macro/regulatory stories still need a real TradingView asset for the image pipeline.
        # BTC is the neutral market-context chart, not a claim that BTC caused the news.
        syms=["BTC"]
    for base in syms[:2]:
        s=str(base).upper().replace("USDT","")
        if not re.fullmatch(r"[A-Z0-9]{2,10}",s): continue
        pool.append({
            "type":"news","category":"breaking_news" if score>=70 else "news_and_macro",
            "topic":s+"USDT","symbol":s+"USDT","raw_score":round(score,2),
            "reason":"fresh verified news catalyst","title":title[:240],"url":str(article.get("url") or ""),
            "source":str(article.get("source") or ""),"published_at":published,"news_score":score,
        })


def main():
    market=load(MARKET); news=load(NEWS); memory=load(MEMORY); feedback=load(FEEDBACK); publications=recent_publications()
    publication_counts=Counter(); category_counts=Counter(); last_asset_time={}
    observations=rows(memory.get("recent_performance_observations"))
    for row in publications:
        for symbol in row.get("_symbols",set()):
            publication_counts[symbol]+=1; last_asset_time[symbol]=max(last_asset_time.get(symbol,datetime.min.replace(tzinfo=timezone.utc)),row["_dt"])
        if row.get("content_category"): category_counts[str(row["content_category"]).lower()]+=1
    memory_counts=Counter(str(x.get("topic") or "").upper().replace("USDT","") for x in observations if isinstance(x,dict) and x.get("topic"))

    pool=[]
    for item in rows(market.get("top_gainers"))[:10]: add_market_candidate(pool,"top_gainers",item)
    for item in rows(market.get("top_losers"))[:10]: add_market_candidate(pool,"top_losers",item)
    for item in rows(market.get("highest_volume"))[:10]: add_market_candidate(pool,"volume_leaders",item)
    for item in rows(market.get("new_listing_market"))[:10]: add_market_candidate(pool,"new_listings",item,5)
    signals=[x for x in rows(market.get("top_content_signals")) if isinstance(x,dict)]
    for item in sorted(signals,key=lambda x:float(x.get("intraday_range_percent") or 0),reverse=True)[:8]: add_market_candidate(pool,"high_volatility",item,3)
    for item in [x for x in signals if str(x.get("symbol") or "") in {"BTCUSDT","ETHUSDT"}]: add_market_candidate(pool,"technical_setup",item,4)
    for article in rows(news.get("articles")): add_news_candidate(pool,article,market)
    pool=list({(x["type"],x["category"],x["topic"],x.get("title","")):x for x in pool}.values())

    now=datetime.now(timezone.utc)
    for c in pool:
        base=c["topic"][:-4] if c["topic"].endswith("USDT") else c["topic"]
        recent=publication_counts.get(base,0); mem=memory_counts.get(base,0); cat=category_counts.get(c["category"],0)
        cooldown=last_asset_time.get(base); active=bool(cooldown and now-cooldown<timedelta(hours=ASSET_COOLDOWN_HOURS))
        # Fresh material news is not blocked by normal market-asset repetition rules when it is a genuinely new event.
        news_override=c.get("type")=="news"
        penalty=(0 if news_override else min(55,recent*22)+min(54,mem*MEMORY_REPEAT_PENALTY)+min(35,cat*CATEGORY_REPEAT_PENALTY)+(45 if active else 0))
        c.update({"recent_count":recent,"memory_count":mem,"category_recent_count":cat,"cooldown_active":active,"news_override":news_override,"adjusted_score":round(c["raw_score"]-penalty,2),"repeated":False if news_override else (recent>=2 or mem>=MEMORY_HARD_BLOCK_COUNT or active)})

    fresh_news=[c for c in pool if c.get("type")=="news"]
    fresh_news.sort(key=lambda x:x["raw_score"],reverse=True)
    portfolio=load(PORTFOLIO); portfolio_lane=str(portfolio.get("selected_lane") or "").lower()
    feedback_rows=rows(feedback.get("ranked_experiments")); best_experiment=(feedback_rows[0].get("experiment") if feedback_rows and isinstance(feedback_rows[0],dict) else None)
    market_eligible=[c for c in pool if c.get("type")=="market" and not c["repeated"]]
    best_market=max(market_eligible,key=lambda x:x["adjusted_score"],default=None)
    best_news=fresh_news[0] if fresh_news else None

    # Editorial priority: a fresh material story beats a generic mover. Market selection remains the fallback.
    best=best_news if best_news and (best_news["raw_score"]>=NEWS_MATERIAL_SCORE) else best_market
    market_ok=bool(best_market and best_market["adjusted_score"]>=MIN_MARKET_SCORE)
    news_ok=bool(best_news)
    run_ai=bool(news_ok or market_ok)
    if news_ok: reason="fresh_material_news"
    elif market_ok: reason="strong_market_opportunity"
    else: reason="no_strong_opportunity"

    selected=None
    if best:
        selected={
            "category":best["category"],"symbol":best["topic"],"reason":best["reason"],
            "recommended_experiment":best_experiment,
            "instruction":("Lead with the verified news event, explain why it matters now, then connect it to the selected market asset. Do not turn a news story into a generic price recap." if best.get("type")=="news" else f"Use {best['category'].replace('_',' ')} as the starting lane. Prefer a fresh, materially different asset and angle. Do not repeat recent coverage without a major verified event."),
        }
        if best.get("type")=="news":
            selected.update({"news_title":best.get("title"),"news_url":best.get("url"),"news_source":best.get("source"),"news_published_at":best.get("published_at"),"news_score":best.get("news_score")})

    result={"generated_at":now.isoformat(),"run_ai":run_ai,"reason":reason,"selected_opportunity":selected,"candidate_pool":sorted(pool,key=lambda x:x["adjusted_score"],reverse=True)[:32],"best_market_candidate":best_market,"best_news_candidate":best_news,"fresh_news_count":len(fresh_news),"recent_topic_counts":dict(publication_counts),"recent_category_counts":dict(category_counts),"memory_topic_counts":dict(memory_counts),"strategy_memory_loaded":bool(memory),"portfolio_lane":portfolio_lane,"recommended_experiment":best_experiment,"rules":{"min_market_score":MIN_MARKET_SCORE,"news_material_score":NEWS_MATERIAL_SCORE,"news_fresh_minutes":NEWS_FRESH_MINUTES,"asset_cooldown_hours":ASSET_COOLDOWN_HOURS,"breaking_news_override":news_ok,"editorial_lanes":LANES}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": raise SystemExit(main())
