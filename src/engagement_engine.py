"""Deterministic editorial experimentation layer before Gemini.

The creator must optimize for genuine reader actions, not publication count.
No fake engagement is generated. All facts come from scanned data.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFLIGHT = Path("data/live/editorial_preflight.json")
PUBLICATIONS = Path("analytics/publication_log.jsonl")
OUTPUT = Path("data/live/engagement_strategy.json")

EXPERIMENTS = [
    {"id":"A","format":"CHOICE","hook":"surprising market move","question":"A/B choice"},
    {"id":"B","format":"CHART CHALLENGE","hook":"hidden chart signal","question":"Where would you draw the level?"},
    {"id":"C","format":"COIN VS COIN","hook":"two assets diverge","question":"Which one wins?"},
    {"id":"D","format":"DATA SURPRISE","hook":"one unusual number","question":"Did you notice this?"},
    {"id":"E","format":"BREAKOUT OR FAKEOUT","hook":"real technical event","question":"Breakout or fakeout?"},
    {"id":"F","format":"NEWS REACTION","hook":"verified crypto/macro news","question":"Bullish or bearish?"},
    {"id":"G","format":"LIQUIDATION STORY","hook":"sharp flush or squeeze","question":"Reversal or continuation?"},
    {"id":"H","format":"TOP MOVERS","hook":"gainer/loser contrast","question":"Chase, fade, or wait?"},
]

CATEGORIES = {
    "top_gainers": 14, "top_losers": 14, "volume_leaders": 16,
    "new_listings": 18, "high_volatility": 14, "news_and_macro": 18,
    "liquidations": 17, "technical_setup": 12, "comparison": 15,
}

def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default

def recent_publications(hours=168):
    rows=[]
    cutoff=datetime.now(timezone.utc)-timedelta(hours=hours)
    if not PUBLICATIONS.exists(): return rows
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row=json.loads(line)
            dt=datetime.fromisoformat(str(row.get("published_at","")).replace("Z","+00:00"))
            if dt>=cutoff: rows.append(row)
        except Exception: pass
    return rows

def symbol_of(row):
    value=str(row.get("selected_lane_symbol") or row.get("symbol") or row.get("topic") or "").upper().strip()
    return value[:-4] if value.endswith("USDT") else value

def main():
    preflight=load(PREFLIGHT,{})
    candidates=preflight.get("candidate_pool") or []
    pubs=recent_publications()
    assets=Counter(); categories=Counter(); experiments=Counter(); outcomes=[]
    for row in pubs:
        s=symbol_of(row)
        if s: assets[s]+=1
        c=str(row.get("content_category") or row.get("category") or "").lower()
        if c: categories[c]+=1
        e=str(row.get("experiment_id") or row.get("editorial_experiment") or "").upper()
        if e: experiments[e]+=1
        outcomes.append({"symbol":s,"experiment":e,"views":row.get("views"),"likes":row.get("likes"),"replies":row.get("replies"),"shares":row.get("shares"),"followers":row.get("followers_gained")})

    ranked=[]
    for c in candidates:
        s=symbol_of(c); cat=str(c.get("category") or "").lower()
        raw=float(c.get("adjusted_score") or c.get("raw_score") or 0)
        repeat_penalty=min(75,assets.get(s,0)*25) if s else 0
        cat_penalty=min(30,categories.get(cat,0)*6)
        score=raw-repeat_penalty-cat_penalty+CATEGORIES.get(cat,8)+(18 if not assets.get(s) else 0)
        ranked.append({**c,"engagement_score":round(score,2)})
    ranked.sort(key=lambda x:x["engagement_score"],reverse=True)
    selected=ranked[0] if ranked else (preflight.get("best_market_candidate") or {})

    # Prefer an experiment that has not been tested, then one with the weakest
    # recent exposure. This lets the system learn instead of repeating one style.
    tested={e for e,n in experiments.items() if n>0}
    exp=next((x for x in EXPERIMENTS if x["id"] not in tested),None)
    if exp is None:
        # Round-robin after every experiment has at least one observation.
        exp=EXPERIMENTS[len(pubs)%len(EXPERIMENTS)] if EXPERIMENTS else {"id":"A","format":"CHOICE"}

    category=str(selected.get("category") or "news_and_macro").lower()
    interaction={
        "primary_goal":"genuine replies, likes, profile visits and followers",
        "experiment_id":exp["id"],
        "experiment":exp,
        "question_rule":"one low-friction question only; make the answer possible in under 5 seconds",
        "hook_rule":"first line must create curiosity before explaining the numbers",
        "visual_rule":"for a single-asset story, use a real OHLCV candlestick visual whenever candles support the story",
        "avoid":["generic What do you think?","follow/like begging","fake urgency","guaranteed returns","long report","automatic TP/SL"],
        "monetization":"use a relevant cashtag or real chart widget naturally when the asset is discussed; never promise earnings",
    }
    selected=dict(selected)
    selected["instruction"]=(
        f"Choose {category.replace('_',' ')}. Run engagement experiment {exp['id']} ({exp['format']}). "
        f"Hook: {exp['hook']}. End with exactly one easy question: {exp['question']}. "
        "Keep the post concise and conversational. Prefer visual-first storytelling. "
        "Do not repeat a recently covered asset unless there is a major verified new event."
    )
    selected["engagement_strategy"]=interaction

    result={
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "selected":selected,"ranked_candidates":ranked[:15],
        "recent_assets":dict(assets),"recent_categories":dict(categories),
        "experiment_counts":dict(experiments),"experiments":EXPERIMENTS,
        "recent_outcomes":outcomes[-50:],"interaction_blueprint":interaction,
        "learning_note":"Performance metrics must be written back to publication_log after publication; future selection should prefer formats/assets with stronger reply and follower rates, not views alone."
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    preflight["selected_opportunity"]=selected
    preflight["engagement_strategy"]=interaction
    preflight["engagement_ranked_candidates"]=ranked[:15]
    PREFLIGHT.write_text(json.dumps(preflight,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
