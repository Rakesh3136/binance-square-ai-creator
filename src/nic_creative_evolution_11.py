"""NIC Creative Evolution 11.0 — outcome-aware creative diversification.

Builds durable creative fingerprints from publication metadata, joins only explicit
verified rewards, closes reward observations after the seven-day attribution
window, and emits bounded exploration directives for the next publication.
Unknown/unallocated rewards never become negative evidence and are never assigned
to a post without an exact identifier.
"""
from __future__ import annotations
import hashlib,json,re
from collections import Counter
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; PUB=AN/"publication_log.jsonl"
REW=AN/"wte_reward_events.jsonl"; EXT=AN/"external_reward_events.jsonl"
OUT=LIVE/"nic_creative_evolution_11.json"; REPORT=INTEL/"nic_creative_evolution_11_report.json"

LANES=("market_setup","data_investigation","breaking_news","world_macro","research_lesson",
       "education","contrarian_thesis","follow_up","outcome_accountability",
       "weekly_synthesis","nic_learning_note")
FORMATS=("decision_chart","data_story","event_reaction","comparison","mechanism_explainer",
         "contrarian_case","accountability_update","timeline","scenario_map","research_note")
VISUALS=("structure","relationship","volume","event_timeline","cross_asset","comparison",
         "mechanism","scenario_tree","historical_analogue","flow","volatility")

def rows(p):
    out=[]
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def pid(x):
    raw=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or x.get("link") or "").strip().rstrip("/")
    if "/square/post/" in raw: raw=raw.split("/square/post/",1)[1].split("?",1)[0].split("#",1)[0]
    return raw.lower() if re.fullmatch(r"[a-z0-9_-]{1,128}",raw.lower()) else ""

def dt(v):
    try:
        x=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except Exception:return None

def fp(a):
    parts=[a.get("content_lane") or a.get("story_lane") or a.get("story_type"),
           a.get("content_format") or a.get("format"),
           a.get("hook_type"),a.get("craft_pattern"),a.get("visual_type"),
           a.get("reader_payoff_type"),a.get("asset") or a.get("symbol"),
           a.get("cashtag") or a.get("coin_cashtag")]
    canonical="|".join(str(x or "").strip().lower() for x in parts)
    return "cef11-"+hashlib.sha256(canonical.encode()).hexdigest()[:20],canonical

def main():
    now=datetime.now(timezone.utc)
    attrs=[x for x in rows(ATTR) if pid(x)]
    rewards=[x for x in rows(REW) if x.get("verified") is True and x.get("reward_amount_usdc") is not None]
    reward_by_post={}
    unattributed=[]
    for e in rewards:
        p=pid(e)
        if p:
            reward_by_post[p]=reward_by_post.get(p,0.0)+max(0,float(e.get("reward_amount_usdc") or 0))
        else: unattributed.append(e)
    # External notifications are evidence of revenue but remain unallocated unless
    # they carry an exact post identifier.
    for e in rows(EXT):
        p=pid(e)
        if p and e.get("attribution_status") not in ("UNALLOCATED_EXTERNAL_REWARD",):
            reward_by_post[p]=reward_by_post.get(p,0.0)+max(0,float(e.get("reward_amount_usdc") or 0))
    fingerprints=[]; dimensions=Counter(); recent=[]
    for a in attrs:
        f,canonical=fp(a)
        published=dt(a.get("published_at") or a.get("recorded_at"))
        reward=reward_by_post.get(pid(a))
        age_days=(now-published).total_seconds()/86400 if published else None
        if published and age_days is not None and age_days <= 30:
            recent.append(f)
        state="VERIFIED_REWARD" if reward is not None and reward>0 else (
            "VERIFIED_NO_REWARD" if reward is not None else (
                "CLOSED_UNKNOWN" if age_days is not None and age_days>=7 else "UNKNOWN_OPEN"))
        rec={"post_id":pid(a),"fingerprint":f,"fingerprint_basis":canonical,
             "published_at":a.get("published_at") or a.get("recorded_at"),
             "content_lane":a.get("content_lane") or a.get("story_lane"),
             "content_format":a.get("content_format") or a.get("format"),
             "hook_type":a.get("hook_type"),"craft_pattern":a.get("craft_pattern"),
             "visual_type":a.get("visual_type"),"reader_payoff_type":a.get("reader_payoff_type"),
             "reward_state":state,"verified_reward_usdc":round(reward,8) if reward is not None else None,
             "reward_window_closes_at":(published+timedelta(days=7)).isoformat() if published else None}
        fingerprints.append(rec)
        for k in ("content_lane","content_format","hook_type","visual_type","reader_payoff_type"):
            v=str(rec.get(k) or "").strip()
            if v: dimensions[f"{k}:{v}"]+=1
    # Force exploration away from the most recent creative grammar. This is a
    # bounded selector, not a promise of performance.
    recent_set=set(recent[:12])
    candidates=[]
    for lane in LANES:
        for fmt in FORMATS:
            for visual in VISUALS:
                basis=f"{lane}|{fmt}|{visual}"
                f="cef11-"+hashlib.sha256(basis.encode()).hexdigest()[:20]
                if f not in recent_set: candidates.append((f,lane,fmt,visual))
    # Deterministic rotation makes behavior reproducible across runners.
    offset=int(hashlib.sha256(now.strftime("%Y-%m-%d").encode()).hexdigest()[:8],16)%max(1,len(candidates))
    ordered=candidates[offset:]+candidates[:offset]
    directives=[]
    for f,lane,fmt,visual in ordered[:8]:
        directives.append({"fingerprint":f,"lane":lane,"format":fmt,"visual_type":visual,
                           "reason":"explore a creative combination outside the recent fingerprint set",
                           "requires_fresh_evidence":True})
    state={"version":"11.0","status":"READY","generated_at":now.isoformat(),
           "policy":{"explicit_reward_only":True,"unknown_is_neutral":True,
                     "unattributed_rewards_are_not_assigned":True,"seven_day_reward_window_days":7,
                     "recent_fingerprint_window":12,"forced_exploration":True,
                     "creative_fingerprint_is_metadata_not_private_reasoning":True},
           "summary":{"publication_records":len(fingerprints),
                      "verified_reward_posts":sum(x["reward_state"]=="VERIFIED_REWARD" for x in fingerprints),
                      "closed_unknown_posts":sum(x["reward_state"]=="CLOSED_UNKNOWN" for x in fingerprints),
                      "open_unknown_posts":sum(x["reward_state"]=="UNKNOWN_OPEN" for x in fingerprints),
                      "unattributed_verified_reward_events":len(unattributed)},
           "recent_fingerprints":list(dict.fromkeys(recent))[:12],
           "creative_dimensions":dimensions.most_common(50),
           "next_directives":directives,
           "unattributed_rewards":[{"event_id":e.get("event_id"),"observed_at":e.get("observed_at"),
                                   "reward_amount_usdc":e.get("reward_amount_usdc")}
                                  for e in unattributed],
           "fingerprints":fingerprints[-500:]}
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"11.0","status":"READY","summary":state["summary"],
                                  "output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY",**state["summary"],"next_directive":directives[0]}))
if __name__=="__main__": main()
