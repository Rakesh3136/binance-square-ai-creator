"""Distribution + engagement experimentation layer."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
PREFLIGHT=Path("data/live/editorial_preflight.json"); PUBLICATIONS=Path("analytics/publication_log.jsonl"); FEEDBACK=Path("data/live/feedback_strategy.json"); OUTPUT=Path("data/live/engagement_strategy.json")
EXPERIMENTS=[{"id":"A","format":"BREAKING NEWS + MARKET IMPACT","hook":"the event changed the setup","question":"Bullish, bearish, or wait?"},{"id":"B","format":"TRADINGVIEW CHART CHALLENGE","hook":"one level decides the setup","question":"Breakout or fakeout?"},{"id":"C","format":"COIN VS COIN","hook":"two assets are diverging","question":"Which one has the stronger setup?"},{"id":"D","format":"DATA SURPRISE","hook":"one number traders may miss","question":"Did you notice this signal?"},{"id":"E","format":"BREAKOUT / FAKEOUT","hook":"price is testing a decisive level","question":"Would you wait for confirmation?"},{"id":"F","format":"NEWS + CHART","hook":"the headline meets the price action","question":"Does the chart confirm the news?"},{"id":"G","format":"LIQUIDATION STORY","hook":"a sharp flush changed positioning","question":"Reversal or continuation?"},{"id":"H","format":"TOP MOVERS","hook":"today's strongest move has a reason","question":"Chase, fade, or wait?"},{"id":"I","format":"CREATOR CALL OUTCOME","hook":"a previous public call can now be measured","question":"Was the original thesis right?"},{"id":"J","format":"FOLLOW-UP / UPDATE","hook":"the setup changed after the last post","question":"Has the invalidation level changed?"},{"id":"K","format":"EDUCATION FROM LIVE CHART","hook":"one chart pattern explained with real data","question":"Would you trade this pattern?"}]
CATEGORIES={"top_gainers":14,"top_losers":14,"volume_leaders":16,"new_listings":18,"high_volatility":14,"news_and_macro":20,"liquidations":17,"technical_setup":14,"comparison":15,"creator_signal_outcome":18}
def load(path,default):
    try:
        x=json.loads(path.read_text(encoding="utf-8")) if path.exists() else default; return x if isinstance(x,dict) else default
    except Exception:return default
def rows(value): return value if isinstance(value,list) else []
def pubs(hours=336):
    cutoff=datetime.now(timezone.utc)-timedelta(hours=hours); out=[]
    if not PUBLICATIONS.exists():return out
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            r=json.loads(line); dt=datetime.fromisoformat(str(r.get("published_at","")).replace("Z","+00:00"))
            if isinstance(r,dict) and dt>=cutoff:out.append(r)
        except Exception:pass
    return out
def sym(r):
    v=str(r.get("selected_lane_symbol") or r.get("symbol") or r.get("topic") or "").upper().strip(); return v[:-4] if v.endswith("USDT") else v
def metric(r,key):
    try:return float(r.get(key)) if isinstance(r,dict) and r.get(key) is not None else None
    except:return None
def rate(rows_,key,den='views'):
    vals=[(metric(r,key),metric(r,den)) for r in rows_]; vals=[x for x in vals if x[0] is not None and x[1] is not None and x[1]>0]
    return sum(v for v,_ in vals)/sum(d for _,d in vals) if vals else None
def main():
    pre=load(PREFLIGHT,{}); original=pre.get("selected_opportunity") or {}; original=dict(original) if isinstance(original,dict) else {}
    candidates=[x for x in rows(pre.get("candidate_pool")) if isinstance(x,dict)]; history=pubs()
    asset_count=Counter();cat_count=Counter();exp_count=Counter();style_count=Counter();rows_by_exp=defaultdict(list)
    for r in history:
        s=sym(r); c=str(r.get("content_category") or r.get("category") or "").lower(); e=str(r.get("experiment_id") or r.get("editorial_experiment") or "").upper(); st=str(r.get("editorial_style") or r.get("style") or "").strip().upper()
        if s:asset_count[s]+=1
        if c:cat_count[c]+=1
        if e:exp_count[e]+=1;rows_by_exp[e].append(r)
        if st:style_count[st]+=1
    ranked=[]
    for c in candidates:
        s=sym(c);cat=str(c.get("category") or "").lower();raw=metric(c,"adjusted_score") or metric(c,"raw_score") or 0
        repeat=min(80,asset_count.get(s,0)*24) if s else 0; category_repeat=min(30,cat_count.get(cat,0)*5); novelty=20 if not asset_count.get(s) else 0
        ranked.append({**c,"engagement_score":round(raw-repeat-category_repeat+novelty+CATEGORIES.get(cat,8),2)})
    ranked.sort(key=lambda x:x["engagement_score"],reverse=True)
    # Editorial preflight is authoritative. A material news selection must never
    # be replaced by a higher-scoring generic mover during engagement ranking.
    original_news=bool(original.get("news_title") and (original.get("type")=="news" or str(original.get("category") or "").lower() in {"breaking_news","news_and_macro","news_market_impact"} or original.get("news_override")))
    selected=original if original_news else (ranked[0] if ranked else (pre.get("best_market_candidate") if isinstance(pre.get("best_market_candidate"),dict) else {}))
    tested={e for e in exp_count if e}; untested=next((x for x in EXPERIMENTS if x["id"] not in tested),None); exp=untested if untested else max(EXPERIMENTS,key=lambda x:0)
    last_style=str(history[-1].get("editorial_style") or "").upper() if history else ""; previous_style=str(history[-2].get("editorial_style") or "").upper() if len(history)>1 else ""; forbidden={last_style,previous_style}
    if exp["format"] in forbidden:
        alternatives=[x for x in EXPERIMENTS if x["format"] not in forbidden]
        if alternatives:exp=alternatives[0]
    category=str(selected.get("category") or "news_and_macro").lower()
    strategy={"primary_goal":"maximize genuine interaction, follower conversion and useful reader actions; quality beats posting volume","experiment_id":exp["id"],"experiment":exp,"content_coverage":["macro/Fed/inflation/rates","ETF/regulation","security hacks/exploits","major listings/unlocks/upgrades","BTC/ETH/BNB market structure","altcoin leaders/laggards","volume and volatility anomalies","liquidations","new narratives","creator call outcomes","educational chart breakdowns"],"hook_rule":"first 1-2 lines must contain a concrete event, number, level, divergence or surprising observation; never generic introductions","question_rule":"one low-friction question only; prefer A/B, breakout/fakeout, level choice or thesis confirmation","style_rule":"Never repeat the same editorial style, opening cadence, emoji pattern or paragraph structure in consecutive posts. Rotate formats based on evidence and recent history.","writing_rule":"Every post must explain why the information matters, what the chart/news says now, and what would invalidate the thesis when technically supported.","technical_rule":"Single-asset technical stories require the verified TradingView chart and synchronized current price/support/resistance/target/invalidation values. Never invent a level.","creator_tracking_rule":"A creator call becomes an outcome story only after fresh market data verifies the move; measure the result and do not rewrite history.","growth_rule":"Track views, likes, comments, shares and post-attributed follower gains separately. Never convert missing metrics to zero.","monetization_rule":"Use the relevant $cashtag and chart naturally because eligible Square activity can be attributed, but never promise earnings or returns.","avoid":["generic What do you think?","follow/like begging","fake urgency","guaranteed returns","copying another creator","same script template every post","unsupported 10x/20x claims","automatic TP/SL without chart evidence"],"recent_style_counts":dict(style_count)}
    selected=dict(selected)
    authoritative_news=original_news
    if authoritative_news:
        instruction=f"Preserve the verified news story and asset from editorial preflight. Use experiment {exp['id']} ({exp['format']}) only to vary presentation. Hook direction: {exp['hook']}. End with exactly one specific question: {exp['question']}. Lead with the actual verified event and source; explain why it matters; connect only to the selected/news-supported asset(s). Never substitute a generic mover."
    else:
        instruction=f"Use category {category.replace('_',' ')} and experiment {exp['id']} ({exp['format']}). Hook: {exp['hook']}. End with exactly one easy question: {exp['question']}. Make the structure visibly different from the last two posts. Use real evidence only; include a TradingView chart for single-asset technical stories; use verified news when material; use natural cashtag tagging."
    selected["instruction"]=instruction; selected["engagement_strategy"]=strategy
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"selected":selected,"ranked_candidates":ranked[:20],"recent_assets":dict(asset_count),"recent_categories":dict(cat_count),"recent_styles":dict(style_count),"experiment_counts":dict(exp_count),"experiments":EXPERIMENTS,"interaction_blueprint":strategy,"selection_protected":authoritative_news,"selection_source":"editorial_preflight_news" if authoritative_news else "engagement_ranked_candidates","learning_note":"Observed reply/follower rates influence future experiments only after verified evidence exists."}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    # Never overwrite a material news selection with a generic market winner.
    if authoritative_news:
        pre["selected_opportunity"]=original
    else:
        pre["selected_opportunity"]=selected
    pre["engagement_strategy"]=strategy;pre["engagement_ranked_candidates"]=ranked[:20];PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
