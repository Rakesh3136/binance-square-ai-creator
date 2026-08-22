"""Distribution + engagement experimentation layer.

Views alone are not treated as success. The creator rotates hooks, formats,
assets and categories, while keeping a record of outcomes so future choices can
be based on interaction rate rather than raw market score.
"""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFLIGHT=Path("data/live/editorial_preflight.json")
PUBLICATIONS=Path("analytics/publication_log.jsonl")
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
 try:return float(r.get(key) or 0)
 except:return 0.0

def main():
 pre=load(PREFLIGHT,{})
 candidates=pre.get("candidate_pool") or []
 history=pubs()
 asset_count=Counter(); cat_count=Counter(); exp_count=Counter(); perf=defaultdict(lambda:{"posts":0,"views":0,"likes":0,"replies":0,"shares":0,"followers":0})
 for r in history:
  s=sym(r); c=str(r.get("content_category") or r.get("category") or "").lower(); e=str(r.get("experiment_id") or r.get("editorial_experiment") or "").upper()
  if s:asset_count[s]+=1
  if c:cat_count[c]+=1
  if e:exp_count[e]+=1
  keys=[e,c,s]
  for k in keys:
   if not k:continue
   p=perf[k];p["posts"]+=1;p["views"]+=metric(r,"views");p["likes"]+=metric(r,"likes");p["replies"]+=metric(r,"replies");p["shares"]+=metric(r,"shares");p["followers"]+=metric(r,"followers_gained")

 ranked=[]
 for c in candidates:
  s=sym(c);cat=str(c.get("category") or "").lower();raw=metric(c,"adjusted_score") or metric(c,"raw_score")
  repeat=min(80,asset_count.get(s,0)*24) if s else 0
  category_repeat=min(30,cat_count.get(cat,0)*5)
  novelty=20 if not asset_count.get(s) else 0
  interaction=CATEGORIES.get(cat,8)
  score=raw-repeat-category_repeat+novelty+interaction
  ranked.append({**c,"engagement_score":round(score,2)})
 ranked.sort(key=lambda x:x["engagement_score"],reverse=True)
 selected=ranked[0] if ranked else pre.get("best_market_candidate") or {}

 # Prefer an experiment with no test yet. Once tested, choose the experiment
 # with the best reply+follower rate, not the most views.
 tested={e for e in exp_count if e}
 untested=next((x for x in EXPERIMENTS if x["id"] not in tested),None)
 if untested:exp=untested
 else:
  def exp_rate(x):
   p=perf[x["id"]];return (p["replies"]*4+p["likes"]+p["shares"]*2+p["followers"]*5)/max(p["views"],1)
  exp=max(EXPERIMENTS,key=exp_rate)

 category=str(selected.get("category") or "news_and_macro").lower()
 strategy={
  "primary_goal":"maximize genuine interaction and follower conversion, not posting volume",
  "experiment_id":exp["id"],"experiment":exp,
  "distribution_rule":"react to fresh, high-signal opportunities; reject stale moves when their strongest price expansion has already passed",
  "hook_rule":"the first line must create curiosity without sounding like a market report",
  "visual_rule":"single-asset technical story => real OHLCV candlestick chart with only data-supported annotations",
  "question_rule":"one question only; answerable in under 5 seconds; prefer A/B, breakout/fakeout, or a precise chart observation",
  "length_rule":"180-500 characters normally; hard maximum 750 unless genuinely necessary",
  "avoid":["generic What do you think?","follow/like begging","fake urgency","guaranteed returns","long analyst report","automatic TP/SL"],
  "monetization":"use relevant cashtag or real chart widget naturally when supported; never promise earnings",
 }
 selected=dict(selected)
 selected["instruction"]=(f"Use {category.replace('_',' ')} and experiment {exp['id']} ({exp['format']}). "
  f"Hook around {exp['hook']}; end with exactly one easy question: {exp['question']}. "
  "Keep it short, visual-first and conversational. Do not repeat recently covered assets without a major verified event. "
  "If evidence is stale, choose a fresher candidate instead.")
 selected["engagement_strategy"]=strategy

 result={"generated_at":datetime.now(timezone.utc).isoformat(),"selected":selected,"ranked_candidates":ranked[:15],"recent_assets":dict(asset_count),"recent_categories":dict(cat_count),"experiment_counts":dict(exp_count),"experiments":EXPERIMENTS,"performance":{k:v for k,v in perf.items()},"interaction_blueprint":strategy,"learning_note":"Future selection uses reply/like/share/follower rates rather than views alone. A low-view post is not automatically a failure; distribution and engagement are measured separately."}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
 pre["selected_opportunity"]=selected;pre["engagement_strategy"]=strategy;pre["engagement_ranked_candidates"]=ranked[:15];PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding="utf-8")
 print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
