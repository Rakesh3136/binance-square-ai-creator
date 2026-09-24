"""Autonomous self-training controller for the Binance Square creator.

Learns from verified outcomes, audience observations, reliability events and
verified monetization. It changes policy artifacts, not credentials or
authoritative safety/publication gates. Weak samples remain hypotheses.
"""
from __future__ import annotations
import json, hashlib, math
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"creator_self_training.json"; REPORT=INTEL/"creator_self_training_report.json"
MEMORY=AN/"creator_self_training_memory.json"

def load(p, default):
    try:
        if not p.exists(): return default
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def rows_jsonl(p):
    out=[]
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def num(v,d=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else d
    except Exception:return d

def now(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat()
def token(x): return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()[:16]

def main():
    t=now()
    outcomes=rows_jsonl(AN/"creator_7_2_outcomes.jsonl")[-300:]
    pubs=rows_jsonl(AN/"publication_log.jsonl")[-300:]
    perf=rows_jsonl(AN/"square_performance.jsonl")[-300:]
    attribution=rows_jsonl(AN/"publication_attribution.jsonl")[-300:]
    learning=load(LIVE/"creator_22_0_audience_intelligence.json",{})
    revenue=load(LIVE/"revenue_content_director.json",{})
    reliability=load(AN/"creator_10_0_reliability_state.json",{})
    repair=load(AN/"creator_10_1_repair_state.json",{})
    macro=load(LIVE/"global_macro_intelligence.json",{})
    impact=load(LIVE/"cross_asset_impact.json",{})
    prev=load(MEMORY,{"history":[],"priors":{}})

    cutoff=t-timedelta(days=7)
    recent_pubs=[]
    for p in pubs:
        ts=str(p.get("published_at") or p.get("timestamp") or "")
        try:
            dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            if dt>=cutoff: recent_pubs.append(p)
        except Exception:
            recent_pubs.append(p)

    counts=Counter(str(x.get("category") or "unknown").lower() for x in recent_pubs)
    formats=Counter(str(x.get("format") or "unknown").lower() for x in recent_pubs)
    hooks=Counter(str(x.get("hook_type") or "unknown").lower() for x in recent_pubs)

    # Descriptive performance priors. Revenue only enters when the source
    # explicitly records verified revenue/conversions.
    perf_by_post=defaultdict(list)
    for x in perf:
        pid=str(x.get("canonical_post_id") or x.get("post_id") or "").strip()
        if pid: perf_by_post[pid].append(x)
    attr_by_post={str(x.get("canonical_post_id") or x.get("post_id") or "").strip():x for x in attribution if str(x.get("canonical_post_id") or x.get("post_id") or "").strip()}

    observed=[]
    for pid, arr in perf_by_post.items():
        latest=arr[-1]
        metrics=latest.get("metrics") if isinstance(latest.get("metrics"),dict) else latest
        views=num(metrics.get("views") or metrics.get("impressions"))
        replies=num(metrics.get("replies") or metrics.get("comments"))
        shares=num(metrics.get("shares"))
        likes=num(metrics.get("likes"))
        eng=(likes+2*replies+3*shares)/max(views,1) if views>0 else 0
        meta=attr_by_post.get(pid,{})
        observed.append({"post_id":pid,"category":str(meta.get("category") or latest.get("category") or "unknown").lower(),"format":str(meta.get("format") or latest.get("format") or "unknown").lower(),"hook_type":str(meta.get("hook_type") or latest.get("hook_type") or "unknown").lower(),"views":views,"engagement_rate":eng})

    patterns=defaultdict(lambda:{"n":0,"views":0.0,"eng":0.0})
    for x in observed:
        for dim,val in (("category",x["category"]),("format",x["format"]),("hook_type",x["hook_type"])):
            k=(dim,val); patterns[k]["n"]+=1; patterns[k]["views"]+=x["views"]; patterns[k]["eng"]+=x["engagement_rate"]
    repeated=[]
    for (dim,val),g in patterns.items():
        if g["n"]>=3:
            repeated.append({"dimension":dim,"value":val,"samples":g["n"],"avg_views":round(g["views"]/g["n"],2),"avg_engagement_rate":round(g["eng"]/g["n"],8),"evidence":"OBSERVATIONAL_REPEATED"})
    repeated.sort(key=lambda x:(x["avg_engagement_rate"],x["avg_views"]),reverse=True)

    # A soft learning score: repeated audience evidence first, then outcome
    # evidence, with verified monetization as a distinct secondary signal.
    outcome_scores=[num(x.get("outcome_score")) for x in outcomes if x.get("outcome_score") is not None]
    outcome_avg=sum(outcome_scores)/len(outcome_scores) if outcome_scores else None
    revenue_groups=load(AN/"creator_8_0_monetization_engine.json",{})
    verified_revenue=sum(num(revenue_groups.get(k)) for k in ("verified_revenue","allocated_verified_revenue") if revenue_groups.get(k) is not None)

    # Portfolio policy: diversify, but never force a weak topic.
    target_lanes={
      "signal":("capital_flow_long","capital_flow_short","technical_setup","creator_signal_outcome","follow_up"),
      "news_macro":("breaking_news","news_and_macro"),
      "research":("watchlist","comparison","education"),
      "discovery":("top_gainers","top_losers","high_volatility","volume_leaders","new_listings"),
      "meme":("crypto_meme",)
    }
    recent_signal=sum(counts[x] for x in target_lanes["signal"])
    recent_meme=counts["crypto_meme"]
    recent_news=sum(counts[x] for x in target_lanes["news_macro"])
    recent_research=sum(counts[x] for x in target_lanes["research"])

    underrepresented=[]
    if recent_news==0: underrepresented.append("news_macro")
    if recent_research==0: underrepresented.append("research")
    if recent_meme==0: underrepresented.append("meme")
    if recent_signal==0: underrepresented.append("signal")

    failures=[]
    for src in (reliability,repair):
        text=str(src)
        if "BLOCKED" in text.upper(): failures.append("reliability_or_repair_blocked")
    macro_events=num(macro.get("event_count"))
    impact_ready=bool(impact.get("status") in {"READY","NO_IMPACT_DATA"} or impact)
    next_variable="hook_family" if repeated else "content_mix"
    if underrepresented: next_variable="content_lane"
    if failures: next_variable="reliability"

    policy={
      "version":"1.0",
      "generated_at":iso(t),
      "objective":"learn_to_improve_content_quality, audience_return_rate, verified_monetization and reliability",
      "hard_invariants":["never_infer_revenue","never_fake_engagement","never_publish_unsupported_claims","never_force_a_story","never_bypass_authoritative_gates"],
      "learning_method":"descriptive repeated observations + outcome feedback + bounded experiment memory",
      "recent_7d_mix":{"categories":dict(counts),"formats":dict(formats),"hooks":dict(hooks)},
      "observed_patterns":repeated[:25],
      "underrepresented_lanes":underrepresented,
      "macro_context":{"events":macro_events,"impact_layer_ready":impact_ready},
      "verified_monetization":{"verified_revenue_observed":round(verified_revenue,8),"source_policy":"explicit fields only"},
      "outcome_learning":{"resolved_samples":len(outcome_scores),"avg_outcome_score":round(outcome_avg,6) if outcome_avg is not None else None},
      "next_experiment":{"primary_variable":next_variable,"sample_goal":5,"rule":"change one primary editorial variable; compare before/after; keep only observed improvements"},
      "content_portfolio":{"signal_priority_when_verified":True,"news_and_macro_allowed":True,"research_allowed":True,"meme_secondary":True,"do_not_force_underrepresented_lane":True},
      "monetization_contract":{"use_exact_cashtags_or_verified_widgets":True,"quality_before_clicks":True,"duplicate_content_not_repeated":True,"reader_trades_must_never_be_inferred":True},
      "self_development":{"eligible":bool(failures or underrepresented or repeated),"preferred_targets":["prompts","content strategy","editorial scoring","visual strategy","experiments","revenue strategy"],"requires_guarded_validation":True}
    }

    plan_id=token(policy)
    history=prev.get("history") if isinstance(prev.get("history"),list) else []
    history.append({"plan_id":plan_id,"generated_at":iso(t),"primary_variable":next_variable,"underrepresented_lanes":underrepresented,"verified_revenue":round(verified_revenue,8)})
    memory={"version":"1.0","updated_at":iso(t),"last_plan_id":plan_id,"history":history[-100:],"priors":prev.get("priors",{})}

    result={"status":"READY","plan_id":plan_id,"policy":policy,"memory_path":str(MEMORY.relative_to(ROOT))}
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); AN.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","generated_at":iso(t),"plan_id":plan_id,"status":"READY","primary_variable":next_variable,"underrepresented_lanes":underrepresented,"observed_patterns":len(repeated),"resolved_outcomes":len(outcome_scores)},indent=2)+"\\n",encoding="utf-8")
    MEMORY.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+"\\n",encoding="utf-8")
    print(json.dumps({"status":"READY","plan_id":plan_id,"primary_variable":next_variable,"underrepresented_lanes":underrepresented,"observed_patterns":len(repeated),"resolved_outcomes":len(outcome_scores)},indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
