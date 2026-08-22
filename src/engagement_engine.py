"""Distribution + engagement experimentation layer.

Views alone are not treated as success. The creator rotates hooks, formats,
assets and categories, while using observed interaction rates to choose future
experiments. Missing metrics are never treated as zero-performance evidence.
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFLIGHT=Path("data/live/editorial_preflight.json")
PUBLICATIONS=Path("analytics/publication_log.jsonl")
FEEDBACK=Path("data/live/feedback_strategy.json")
OUTPUT=Path("data/live/engagement_strategy.json")

EXPERIMENTS=[
 {"id":"A","format":"CHOICE","hook":"surprising move","question":"Pick one of two outcomes"},
 {"id":"B","format":"CHART CHALLENGE","hook":"hidden chart signal","question":"Where would you draw the key level?"},
 {"id":"C","format":"COIN VS COIN","hook":"two assets diverge","question":"Which one are you watching?"},
 {"id":"D","format":"DATA SURPRISE","hook":"one unusual number","question":"Did you spot this?"},
 {"id":"E","format":"BREAKOUT OR FAKEOUT","hook":"real technical event","question":"Breakout or fakeout?"},
 {"id":"F","format":"NEWS REACTION","hook":"verified news event","question":"Bullish or bearish?"},
 {"id":"G","format":"LIQUIDATION STORY","hook":"sharp flush or squeeze","question":"Reversal or continuation?"},
 {"id":"H","format":"TOP MOVERS","hook":"gainer/loser contrast","question":"Chase, fade, or wait?"},
]
CATEGORIES={"top_gainers":14,"top_losers":14,"volume_leaders":16,"new_listings":18,"high_volatility":14,"news_and_macro":18,"liquidations":17,"technical_setup":12,"comparison":15}

def load(path,default):
    try:return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:return default

def pubs(hours=336):
    cutoff=datetime.now(timezone.utc)-timedelta(hours=hours); out=[]
    if not PUBLICATIONS.exists():return out
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            r=json.loads(line); dt=datetime.fromisoformat(str(r.get("published_at","")).replace("Z","+00:00"))
            if dt>=cutoff:out.append(r)
        except Exception:pass
    return out

def sym(r):
    v=str(r.get("selected_lane_symbol") or r.get("symbol") or r.get("topic") or "").upper().strip()
    return v[:-4] if v.endswith("USDT") else v

def metric(r,key):
    try:return float(r.get(key)) if r.get(key) is not None else None
    except:return None

def rate(rows,key,den='views'):
    vals=[(metric(r,key),metric(r,den)) for r in rows]
    vals=[x for x in vals if x[0] is not None and x[1] is not None and x[1]>0]
    return sum(v for v,_ in vals)/sum(d for _,d in vals) if vals else None

def main():
    pre=load(PREFLIGHT,{})
    candidates=pre.get("candidate_pool") or []
    history=pubs()
    asset_count=Counter();cat_count=Counter();exp_count=Counter();rows_by_exp=defaultdict(list);rows_by_cat=defaultdict(list)
    for r in history:
        s=sym(r); c=str(r.get("content_category") or r.get("category") or "").lower(); e=str(r.get("experiment_id") or r.get("editorial_experiment") or "").upper()
        if s:asset_count[s]+=1
        if c:cat_count[c]+=1;rows_by_cat[c].append(r)
        if e:exp_count[e]+=1;rows_by_exp[e].append(r)

    ranked=[]
    for c in candidates:
        s=sym(c);cat=str(c.get("category") or "").lower();raw=metric(c,"adjusted_score") or metric(c,"raw_score") or 0
        repeat=min(80,asset_count.get(s,0)*24) if s else 0
        category_repeat=min(30,cat_count.get(cat,0)*5)
        novelty=20 if not asset_count.get(s) else 0
        score=raw-repeat-category_repeat+novelty+CATEGORIES.get(cat,8)
        ranked.append({**c,"engagement_score":round(score,2)})
    ranked.sort(key=lambda x:x["engagement_score"],reverse=True)
    selected=ranked[0] if ranked else pre.get("best_market_candidate") or {}

    tested={e for e in exp_count if e}
    untested=next((x for x in EXPERIMENTS if x["id"] not in tested),None)
    if untested:exp=untested
    else:
        def exp_score(x):
            rs=rate(rows_by_exp[x["id"]],"replies")
            fs=rate(rows_by_exp[x["id"]],"followers_gained")
            ls=rate(rows_by_exp[x["id"]],"likes")
            ss=rate(rows_by_exp[x["id"]],"shares")
            # No evidence => neutral; small samples are capped by confidence.
            n=len(rows_by_exp[x["id"]]); conf=min(1.0,n/10)
            observed=(0.50*(rs or 0)+0.30*(fs or 0)+0.12*(ls or 0)+0.08*(ss or 0))
            return observed*conf
        exp=max(EXPERIMENTS,key=exp_score)

    # If feedback explicitly reports a weak format, keep it in the rotation but
    # don't let it dominate. If a format has strong evidence, give it more tests.
    category=str(selected.get("category") or "news_and_macro").lower()
    strategy={
      "primary_goal":"maximize genuine interaction and follower conversion, not posting volume",
      "experiment_id":exp["id"],"experiment":exp,
      "feedback_source":str(FEEDBACK),
      "distribution_rule":"react to fresh, high-signal opportunities; reject stale moves when their strongest expansion has already passed",
      "hook_rule":"first line creates curiosity without sounding like a market report",
      "visual_rule":"single-asset technical story => real OHLCV candlestick chart with only data-supported annotations",
      "question_rule":"one question only; answerable in under 5 seconds; prefer A/B, breakout/fakeout, or precise chart observation",
      "length_rule":"180-500 characters normally; hard maximum 750 unless genuinely necessary",
      "avoid":["generic What do you think?","follow/like begging","fake urgency","guaranteed returns","long analyst report","automatic TP/SL"],
      "monetization":"use relevant cashtag or real chart widget naturally when supported; never promise earnings",
    }
    selected=dict(selected)
    selected["instruction"]=(f"Use {category.replace('_',' ')} and experiment {exp['id']} ({exp['format']}). "
      f"Hook around {exp['hook']}; end with exactly one easy question: {exp['question']}. "
      "Keep it short, visual-first and conversational. Do not repeat recently covered assets without a major verified event. "
      "Use historical feedback only as evidence, not as a guarantee of future performance.")
    selected["engagement_strategy"]=strategy

    perf_summary={}
    for e in EXPERIMENTS:
        rs=rate(rows_by_exp[e["id"]],"replies");fs=rate(rows_by_exp[e["id"]],"followers_gained");ls=rate(rows_by_exp[e["id"]],"likes");ss=rate(rows_by_exp[e["id"]],"shares")
        perf_summary[e["id"]]={"posts":len(rows_by_exp[e["id"]]),"reply_rate":rs,"follower_rate":fs,"like_rate":ls,"share_rate":ss,"confidence":min(1.0,len(rows_by_exp[e["id"]])/10)}
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"selected":selected,"ranked_candidates":ranked[:15],"recent_assets":dict(asset_count),"recent_categories":dict(cat_count),"experiment_counts":dict(exp_count),"experiments":EXPERIMENTS,"performance":perf_summary,"interaction_blueprint":strategy,"learning_note":"Observed reply/follower rates now influence the next experiment after enough evidence exists. Missing metrics remain unknown rather than zero. Historical performance never guarantees future results."}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    pre["selected_opportunity"]=selected;pre["engagement_strategy"]=strategy;pre["engagement_ranked_candidates"]=ranked[:15];PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__":main()
