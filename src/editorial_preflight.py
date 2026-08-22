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
NEWS_FRESH_MINUTES = 35
MEMORY_REPEAT_PENALTY = 18.0
MEMORY_HARD_BLOCK_COUNT = 3
CATEGORY_REPEAT_PENALTY = 14.0
ASSET_COOLDOWN_HOURS = 12
LANES = ["top_gainers", "top_losers", "volume_leaders", "new_listings", "high_volatility", "news_and_macro", "technical_setup", "comparison", "education"]


def load(path):
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}


def extract_symbols(text):
    found=set()
    for token in re.findall(r"(?<![A-Z0-9])\$?[A-Z][A-Z0-9]{1,11}(?:USDT)?(?![A-Z0-9])", str(text or "").upper()):
        clean=token.replace("$",""); base=clean[:-4] if clean.endswith("USDT") else clean
        if 2 <= len(base) <= 10: found.add(base)
    return found


def recent_publications():
    rows=[]; cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    if not PUBLICATIONS.exists(): return rows
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row=json.loads(line); dt=datetime.fromisoformat(str(row.get("published_at","")).replace("Z","+00:00"))
            if dt >= cutoff:
                raw=" ".join(str(row.get(k) or "") for k in ("symbol","selected_lane_symbol","topic"))
                rows.append({**row,"_symbols":extract_symbols(raw),"_dt":dt})
        except Exception: pass
    return rows


def add_market_candidate(pool, category, item, boost=0.0):
    if not item: return
    symbol=str(item.get("symbol") or "").upper()
    if not symbol: return
    raw=float(item.get("content_signal_score") or 0)
    if category in {"top_gainers","top_losers"}:
        raw=min(100.0,abs(float(item.get("price_change_percent") or 0))*4.5+float(item.get("intraday_range_percent") or 0))
    elif category=="volume_leaders": raw=min(100.0,raw+10.0)
    elif category=="new_listings": raw=min(100.0,raw+max(0.0,25.0-float(item.get("days_since_listing") or 30)*3.0))
    pool.append({"type":"market","category":category,"topic":symbol,"raw_score":round(min(100.0,raw+boost),2),"reason":category})


def main():
    market=load(MARKET); news=load(NEWS); memory=load(MEMORY); feedback=load(FEEDBACK); publications=recent_publications()
    publication_counts=Counter(); category_counts=Counter(); last_asset_time={}
    for row in publications:
        for symbol in row.get("_symbols",set()):
            publication_counts[symbol]+=1; last_asset_time[symbol]=max(last_asset_time.get(symbol,datetime.min.replace(tzinfo=timezone.utc)),row["_dt"])
        if row.get("content_category"): category_counts[str(row["content_category"]).lower()]+=1
    memory_counts=Counter(str(x.get("topic") or "").upper().replace("USDT","") for x in memory.get("recent_performance_observations") or [] if x.get("topic"))

    pool=[]
    for item in (market.get("top_gainers") or [])[:10]: add_market_candidate(pool,"top_gainers",item)
    for item in (market.get("top_losers") or [])[:10]: add_market_candidate(pool,"top_losers",item)
    for item in (market.get("highest_volume") or [])[:10]: add_market_candidate(pool,"volume_leaders",item)
    for item in (market.get("new_listing_market") or [])[:10]: add_market_candidate(pool,"new_listings",item,5)
    signals=market.get("top_content_signals") or []
    for item in sorted(signals,key=lambda x:float(x.get("intraday_range_percent") or 0),reverse=True)[:8]: add_market_candidate(pool,"high_volatility",item,3)
    for item in [x for x in signals if str(x.get("symbol") or "") in {"BTCUSDT","ETHUSDT"}]: add_market_candidate(pool,"technical_setup",item,4)
    pool=list({(x["category"],x["topic"]):x for x in pool}.values())

    now=datetime.now(timezone.utc)
    for c in pool:
        base=c["topic"][:-4] if c["topic"].endswith("USDT") else c["topic"]
        recent=publication_counts.get(base,0); mem=memory_counts.get(base,0); cat=category_counts.get(c["category"],0)
        cooldown=last_asset_time.get(base); active=bool(cooldown and now-cooldown<timedelta(hours=ASSET_COOLDOWN_HOURS))
        c.update({"recent_count":recent,"memory_count":mem,"category_recent_count":cat,"cooldown_active":active,"adjusted_score":round(c["raw_score"]-min(55,recent*22)-min(54,mem*MEMORY_REPEAT_PENALTY)-min(35,cat*CATEGORY_REPEAT_PENALTY)-(45 if active else 0),2),"repeated":recent>=2 or mem>=MEMORY_HARD_BLOCK_COUNT or active})

    fresh_news=0
    for article in news.get("articles") or []:
        try:
            dt=datetime.fromisoformat(str(article.get("published_at","")).replace("Z","+00:00"))
            if now-dt<=timedelta(minutes=NEWS_FRESH_MINUTES): fresh_news+=1
        except Exception: pass

    # Portfolio planner can suggest a lane, while feedback determines whether we should
    # favor an experiment. It never overrides a verified breaking-news opportunity.
    portfolio_lane=str((load(PORTFOLIO).get("selected_lane") or "")).lower()
    feedback_rows=feedback.get("ranked_experiments") or []
    best_experiment=(feedback_rows[0].get("experiment") if feedback_rows else None)
    eligible=[c for c in pool if not c["repeated"]] or [c for c in pool if c["adjusted_score"]>0]
    if portfolio_lane:
        lane_candidates=[c for c in eligible if c["category"]==portfolio_lane]
        if lane_candidates: eligible=lane_candidates+ [c for c in eligible if c not in lane_candidates]
    best=max(eligible,key=lambda x:x["adjusted_score"],default=None)
    market_ok=bool(best and best["adjusted_score"]>=MIN_MARKET_SCORE)
    run_ai=market_ok or fresh_news>0
    reason="fresh_news" if fresh_news>0 and not market_ok else ("strong_market_opportunity" if market_ok else "no_strong_opportunity")
    selected=None
    if best:
        selected={"category":best["category"],"symbol":best["topic"],"reason":best["reason"],"recommended_experiment":best_experiment,"instruction":f"Use {best['category'].replace('_',' ')} as the starting lane. Prefer a fresh, materially different asset and angle. Do not repeat recent coverage without a major verified event."}
    result={"generated_at":now.isoformat(),"run_ai":run_ai,"reason":reason,"selected_opportunity":selected,"candidate_pool":sorted(pool,key=lambda x:x["adjusted_score"],reverse=True)[:24],"best_market_candidate":best,"fresh_news_count":fresh_news,"recent_topic_counts":dict(publication_counts),"recent_category_counts":dict(category_counts),"memory_topic_counts":dict(memory_counts),"strategy_memory_loaded":bool(memory),"portfolio_lane":portfolio_lane,"recommended_experiment":best_experiment,"rules":{"min_market_score":MIN_MARKET_SCORE,"asset_cooldown_hours":ASSET_COOLDOWN_HOURS,"breaking_news_override":fresh_news>0,"editorial_lanes":LANES}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": raise SystemExit(main())
