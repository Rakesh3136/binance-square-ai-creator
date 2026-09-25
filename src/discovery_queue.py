"""Persistent discovery backlog for differentiated Square content.

This queue keeps evidence-backed ideas alive across 20-minute sensing cycles so
a strong discovery is not lost just because another lane won one cycle.
It never bypasses publication, originality, evidence, Jev or production gates.
"""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"data/live/discovery_queue.json"
BRIEF=ROOT/"data/live/content_director_brief.json"
PREF=ROOT/"data/live/editorial_preflight.json"
RANKING=ROOT/"data/live/opportunity_ranking_6.json"
KNOWLEDGE={"education","research_insight","market_mechanism","data_surprise","watchlist","comparison"}
MAX_ITEMS=200
MIN_SCORE=55

def load(path, default):
    try:
        value=json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        return value if isinstance(value,type(default)) else default
    except Exception:
        return default

def category(x):
    return str(x.get("category") or x.get("lane") or x.get("content_category") or "").lower() if isinstance(x,dict) else ""

def symbol(x):
    return str(x.get("symbol") or "").upper().replace("BINANCE:","").replace("$","").replace("USDT","").strip() if isinstance(x,dict) else ""

def signature(x):
    basis={
        "symbol":symbol(x),
        "category":category(x),
        "content_intent":str(x.get("content_intent") or "").lower(),
        "title":str(x.get("title") or x.get("news_title") or x.get("topic") or "").strip().lower()
    }
    return hashlib.sha1(json.dumps(basis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]

def normalize(x, now):
    c=dict(x)
    c["queue_id"]=signature(c)
    c["queued_at"]=str(c.get("queued_at") or now)
    c["last_seen_at"]=now
    c["queue_category"]=category(c)
    c["queue_symbol"]=symbol(c)
    return c

def eligible(x):
    if not isinstance(x,dict):
        return False
    cat=category(x); s=symbol(x)
    if not s and cat not in KNOWLEDGE:
        return False
    try: score=float(x.get("score",x.get("ranker_score",0)))
    except Exception: score=0.0
    if score < MIN_SCORE:
        return False
    if cat in KNOWLEDGE:
        research=x.get("research") if isinstance(x.get("research"),dict) else {}
        evidence=max(float(x.get("evidence_score") or 0),float(research.get("evidence_score") or 0),
                     float(research.get("information_advantage_score") or 0)*0.7+
                     float(research.get("undercoverage_score") or 0)*0.3)
        return evidence >= 55
    return True

def main():
    now=datetime.now(timezone.utc).isoformat()
    state=load(QUEUE,{"version":"1.0","candidates":[]})
    existing=state.get("candidates") if isinstance(state.get("candidates"),list) else []
    by_id={str(x.get("queue_id")):x for x in existing if isinstance(x,dict) and x.get("queue_id")}

    brief=load(BRIEF,{})
    pref=load(PREF,{})
    ranking=load(RANKING,{})
    incoming=[]
    incoming.extend(x for x in brief.get("ranked_stories",[]) if isinstance(x,dict))
    incoming.extend(x for x in (ranking.get("top_candidates") or []) if isinstance(x,dict))
    selected=ranking.get("selected")
    if isinstance(selected,dict): incoming.append(selected)
    selected=brief.get("authoritative_selection")
    if isinstance(selected,dict): incoming.append(selected)
    selected=pref.get("selected_opportunity")
    if isinstance(selected,dict): incoming.append(selected)

    added=0; refreshed=0
    for raw in incoming:
        if not eligible(raw): continue
        item=normalize(raw,now); qid=item["queue_id"]
        if qid in by_id:
            old=by_id[qid]
            old["candidate"]=item
            old["last_seen_at"]=now
            try:
                old_score=float(item.get("score",item.get("ranker_score",0)))
                if old_score > float(old.get("best_score") or 0):
                    old["best_score"]=old_score
            except Exception: pass
            refreshed+=1
        else:
            by_id[qid]={"queue_id":qid,"candidate":item,"queued_at":now,"last_seen_at":now,"best_score":float(item.get("score",item.get("ranker_score",0)) or 0)}
            added+=1

    cutoff=datetime.now(timezone.utc)-timedelta(days=14)
    kept=[]
    for item in by_id.values():
        seen=item.get("last_seen_at") or item.get("queued_at")
        try: dt=datetime.fromisoformat(str(seen).replace("Z","+00:00"))
        except Exception: dt=datetime.now(timezone.utc)
        if dt>=cutoff:
            kept.append(item)
    kept.sort(key=lambda x:(float(x.get("best_score") or 0),str(x.get("last_seen_at") or "")),reverse=True)
    state={
        "version":"1.0-persistent-discovery-backlog",
        "generated_at":now,
        "candidate_count":len(kept[:MAX_ITEMS]),
        "added_this_cycle":added,
        "refreshed_this_cycle":refreshed,
        "candidates":kept[:MAX_ITEMS],
        "policy":{
            "persistent_across_cycles":True,
            "max_items":MAX_ITEMS,
            "retention_days":14,
            "minimum_score":MIN_SCORE,
            "knowledge_lanes":sorted(KNOWLEDGE),
            "publication_gates_remain_authoritative":True
        }
    }
    QUEUE.parent.mkdir(parents=True,exist_ok=True)
    QUEUE.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","candidate_count":len(kept[:MAX_ITEMS]),"added_this_cycle":added,"refreshed_this_cycle":refreshed},ensure_ascii=False))

if __name__=="__main__":
    main()
