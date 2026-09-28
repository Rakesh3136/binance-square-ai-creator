"""Bounded NIC self-training controller.

Learns from recorded outcomes and publication metadata. This module produces
policy telemetry only; it never bypasses authoritative publication gates.
"""
from __future__ import annotations
import hashlib, json, math, re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"creator_self_training.json"; REPORT=INTEL/"creator_self_training_report.json"; MEMORY=AN/"creator_self_training_memory.json"

def load(p, default):
    try:
        if not p.exists(): return default
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception: return default

def rows(p):
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            v=json.loads(line)
            if isinstance(v,dict): out.append(v)
        except Exception: pass
    return out

def num(v,d=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else d
    except Exception: return d

def fingerprint(text): return set(re.findall(r"[a-z0-9]{3,}",str(text or "").lower()))
def overlap(a,b):
    x,y=fingerprint(a),fingerprint(b)
    return round(len(x&y)/max(len(x|y),1),4) if x and y else 0.0

def main():
    now=datetime.now(timezone.utc); pubs=rows(AN/"publication_log.jsonl")[-300:]; perf=rows(AN/"square_performance.jsonl")[-300:]; outcomes=rows(AN/"creator_7_2_outcomes.jsonl")[-300:]
    cutoff=now-timedelta(days=7); recent=[]
    for p in pubs:
        ts=str(p.get("published_at") or p.get("timestamp") or "")
        try:
            dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            if dt>=cutoff: recent.append(p)
        except Exception: recent.append(p)
    categories=Counter(str(x.get("category") or "unknown").lower() for x in recent)
    formats=Counter(str(x.get("format") or "unknown").lower() for x in recent)
    texts=[str(x.get("post") or x.get("text") or x.get("title") or "") for x in recent if str(x.get("post") or x.get("text") or x.get("title") or "").strip()]
    overlaps=[]
    for i,current in enumerate(texts[-10:]):
        prior=texts[:max(0,len(texts)-len(texts[-10:])+i)]
        if prior: overlaps.append(max(overlap(current,x) for x in prior))
    outcome_scores=[num(x.get("outcome_score")) for x in outcomes if x.get("outcome_score") is not None]
    avg=sum(outcome_scores)/len(outcome_scores) if outcome_scores else None
    lanes={"news_macro":sum(categories[x] for x in ("breaking_news","news_and_macro")),"research":sum(categories[x] for x in ("watchlist","comparison","education")),"meme":categories["crypto_meme"],"signal":sum(categories[x] for x in ("capital_flow_long","capital_flow_short","technical_setup","creator_signal_outcome","follow_up"))}
    under=[k for k,v in lanes.items() if v==0]
    next_variable="content_lane" if under else ("hook_family" if recent else "content_mix")
    state={
      "status":"READY","version":"1.2","generated_at":now.isoformat(),
      "policy":{"hard_invariants":["never_infer_revenue","never_fake_engagement","never_publish_unsupported_claims","never_force_a_story","never_bypass_authoritative_gates"],"learning_method":"descriptive_observations_plus_verified_outcomes","semantic_novelty":"diagnostic_only"},
      "recent_7d_mix":{"categories":dict(categories),"formats":dict(formats)},
      "semantic_novelty":{"recent_comparable_posts":len(texts),"average_token_overlap":round(sum(overlaps)/len(overlaps),4) if overlaps else None,"max_token_overlap":max(overlaps) if overlaps else None},
      "underrepresented_lanes":under,
      "outcome_learning":{"resolved_samples":len(outcome_scores),"avg_outcome_score":round(avg,6) if avg is not None else None},
      "next_experiment":{"primary_variable":next_variable,"sample_goal":5,"rule":"change_one_variable_and_keep_only_observed_improvements"},
      "self_development":{"eligible":bool(under or overlaps),"requires_guarded_validation":True}
    }
    plan_id=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()[:16]
    state["plan_id"]=plan_id
    previous=load(MEMORY,{"history":[]}); history=previous.get("history") if isinstance(previous.get("history"),list) else []
    history.append({"plan_id":plan_id,"generated_at":now.isoformat(),"primary_variable":next_variable,"underrepresented_lanes":under})
    memory={"version":"1.2","updated_at":now.isoformat(),"last_plan_id":plan_id,"history":history[-100:]}
    for p,v in ((OUT,state),(REPORT,{"version":"1.2","generated_at":now.isoformat(),"plan_id":plan_id,"status":"READY","primary_variable":next_variable,"underrepresented_lanes":under}),(MEMORY,memory)):
        p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","plan_id":plan_id,"primary_variable":next_variable}))

if __name__=="__main__": main()
