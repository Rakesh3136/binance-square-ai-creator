"""NIC Attribution Intelligence 7.0 — canonical post-to-outcome learning ledger.

Joins publication lineage, explicit Square performance, and explicitly verified
Write-to-Earn reward events by canonical post id. Missing evidence remains
UNKNOWN. Views, likes, comments, and prediction outcomes never become revenue.
"""
from __future__ import annotations
import hashlib, json, math, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ANALYTICS=ROOT/"analytics"
LIVE=ROOT/"data/live"
INTEL=ROOT/"data/intelligence"
ATTR=ANALYTICS/"publication_attribution.jsonl"
PERF=ANALYTICS/"square_performance.jsonl"
REWARDS=ANALYTICS/"wte_reward_events.jsonl"
OUT=LIVE/"nic_attribution_intelligence_7.json"
LEDGER=ANALYTICS/"nic_attribution_events.jsonl"
REPORT=INTEL/"nic_attribution_intelligence_7_report.json"
STORY=LIVE/"nic_story_discovery.json"

def load_jsonl(path: Path):
    rows=[]
    if not path.exists(): return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): rows.append(x)
        except Exception: pass
    return rows

def pid(x):
    raw=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or x.get("link") or "").strip().rstrip("/")
    if "/square/post/" in raw:
        raw=raw.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0]
    return raw.lower() if re.fullmatch(r"[a-z0-9_-]{1,128}",raw.lower()) else ""

def num(x,*keys):
    for k in keys:
        try:
            v=float(x.get(k))
            if math.isfinite(v): return v
        except (TypeError,ValueError): pass
    return None

def reward_map():
    out={}
    for e in load_jsonl(REWARDS):
        p=pid(e)
        if not p or e.get("verified") is not True or e.get("reward_amount_usdc") is None:
            continue
        amount=num(e,"reward_amount_usdc")
        if amount is None or amount < 0:
            continue
        bucket=out.setdefault(p, {"amount": 0.0, "events": 0, "last": e})
        bucket["amount"] += amount
        bucket["events"] += 1
        bucket["last"] = e
    return out

def stable_id(post_id, recorded_at):
    return "nia7-"+hashlib.sha256(f"{post_id}:{recorded_at}".encode()).hexdigest()[:20]

def main():
    now=datetime.now(timezone.utc).isoformat()
    attrs={pid(x):x for x in load_jsonl(ATTR) if pid(x)}
    perf={pid(x):x for x in load_jsonl(PERF) if pid(x)}
    rewards=reward_map()
    rows=[]
    for post,a in attrs.items():
        p=perf.get(post,{})
        e=rewards.get(post)
        reward=round(float(e["amount"]),8) if e else None
        if e is not None and reward > 0:
            outcome="VERIFIED_REWARD"
        elif e is not None and reward == 0:
            outcome="VERIFIED_NO_REWARD"
        else:
            outcome="UNKNOWN"
        rows.append({
            "attribution_event_id":stable_id(post,str(a.get("published_at") or a.get("recorded_at") or "")),
            "post_id":post,
            "published_at":a.get("published_at") or a.get("recorded_at"),
            "symbol":a.get("symbol"),
            "story_id":a.get("story_id"),
            "story_type":a.get("story_type") or a.get("story_kind"),
            "craft_id":a.get("craft_id"),
            "craft_pattern":a.get("craft_pattern"),
            "content_lane":a.get("content_lane") or a.get("story_lane"),
            "content_format":a.get("content_format") or a.get("format"),
            "hook_type":a.get("hook_type"),
            "visual_type":a.get("visual_type"),
            "reader_payoff_type":a.get("reader_payoff_type"),
            "experiment_id":a.get("experiment_id"),
            "experiment_variable":a.get("experiment_variable"),
            "experiment_treatment":a.get("experiment_treatment"),
            "cycle_id":a.get("cycle_id"),
            "cashtag":a.get("cashtag") or a.get("coin_cashtag"),
            "publication_proof":a.get("publication_proof"),
            "performance": {
                "views":num(p,"views","view_count","impressions"),
                "likes":num(p,"likes","like_count"),
                "comments":num(p,"comments","reply_count"),
                "shares":num(p,"shares","share_count"),
            },
            "outcome_state":outcome,
            "verified_reward_usdc":reward,
            "reward_source":e["last"].get("source") if e else None,
            "reward_event_verified_at":e["last"].get("observed_at") if e else None,
            "verified_reward_event_count":e["events"] if e else 0,
            "evidence_policy":"explicit_reward_only; missing_reward_is_unknown",
        })
    rows.sort(key=lambda x:str(x.get("published_at") or ""))
    story_groups=defaultdict(lambda:{"posts":0,"verified_rewards":0,"verified_revenue_usdc":0.0,"unknown":0})
    lane_groups=defaultdict(lambda:{"posts":0,"verified_rewards":0,"verified_revenue_usdc":0.0,"unknown":0})
    for r in rows:
        sg=str(r.get("story_id") or r.get("story_type") or "unknown")
        lg=str(r.get("content_lane") or "unknown")
        for key,g in ((sg,story_groups),(lg,lane_groups)):
            g[key]["posts"]+=1
            if r["outcome_state"]=="VERIFIED_REWARD":
                g[key]["verified_rewards"]+=1
                g[key]["verified_revenue_usdc"]+=float(r["verified_reward_usdc"] or 0)
            else: g[key]["unknown"]+=1
    story_priors=[]
    for key,g in story_groups.items():
        story_priors.append({"story_key":key,**g,"verified_revenue_usdc":round(g["verified_revenue_usdc"],8),
                             "learning_state":"VERIFIED_SIGNAL" if g["verified_rewards"] else "INSUFFICIENT_REWARD_EVIDENCE"})
    lane_priors=[]
    for key,g in lane_groups.items():
        lane_priors.append({"lane":key,**g,"verified_revenue_usdc":round(g["verified_revenue_usdc"],8),
                            "learning_state":"VERIFIED_SIGNAL" if g["verified_rewards"] else "INSUFFICIENT_REWARD_EVIDENCE"})
    state={
      "version":"7.0","generated_at":now,"status":"READY",
      "summary":{
        "attributed_posts":len(rows),
        "verified_reward_posts":sum(r["outcome_state"]=="VERIFIED_REWARD" for r in rows),
        "verified_no_reward_posts":sum(r["outcome_state"]=="VERIFIED_NO_REWARD" for r in rows),
        "unknown_reward_posts":sum(r["outcome_state"]=="UNKNOWN" for r in rows),
        "verified_reward_total_usdc":round(sum(float(r["verified_reward_usdc"] or 0) for r in rows),8),
      },
      "evidence_policy":{
        "join_key":"canonical_post_id",
        "reward_requires_verified_true_and_explicit_reward_amount_usdc":True,
        "views_are_reach_not_revenue":True,
        "engagement_is_not_revenue":True,
        "missing_reward_is_UNKNOWN":True,
        "unattributed_rewards_are_not_assigned":True,
        "prediction_success_is_not_revenue":True,
      },
      "learning":{
        "story_priors":story_priors[:100],
        "lane_priors":lane_priors[:50],
        "instruction":"Use verified signals only as bounded evidence. UNKNOWN means collect more data, not failure.",
      },
      "posts":rows[-500:],
      "unattributed_verified_rewards":[
        {"event_id":e.get("event_id"),"observed_at":e.get("observed_at"),"reward_amount_usdc":num(e,"reward_amount_usdc"),"source":e.get("source")}
        for e in load_jsonl(REWARDS) if e.get("verified") is True and e.get("reward_amount_usdc") is not None and not pid(e)
      ],
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); ANALYTICS.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    try:
        output_ref=str(OUT.relative_to(ROOT))
    except ValueError:
        # Tests may redirect output into an isolated temporary root. Preserve
        # the real output location instead of crashing on an unrelated path.
        output_ref=str(OUT)
    REPORT.write_text(json.dumps({"version":"7.0","status":"READY",**state["summary"],"output":output_ref},indent=2)+"\n",encoding="utf-8")
    existing={str(x.get("attribution_event_id")) for x in load_jsonl(LEDGER)}
    with LEDGER.open("a",encoding="utf-8") as h:
        for r in rows:
            if r["attribution_event_id"] in existing: continue
            h.write(json.dumps(r,ensure_ascii=False)+"\n")
    story= {}
    try:
        story=json.loads(STORY.read_text(encoding="utf-8")) if STORY.exists() else {}
    except Exception: story={}
    state["story_discovery_feedback"]={
        "available":bool(story),
        "verified_signal_count":sum(1 for r in rows if r["outcome_state"]=="VERIFIED_REWARD"),
        "unknown_count":sum(1 for r in rows if r["outcome_state"]=="UNKNOWN"),
        "do_not_promote_unknown_to_negative":True,
    }
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(state["summary"],ensure_ascii=False))

if __name__=="__main__":
    main()
