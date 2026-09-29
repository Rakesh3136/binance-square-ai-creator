"""NIC Content Master 10.0 — bounded evidence-based craft learning.

Learns from verified publication outcomes which editorial patterns deserve more
or less exploration. Missing reward telemetry remains UNKNOWN and is neutral.
This module never grants publish permission, invents revenue, or exposes
private reasoning.
"""
from __future__ import annotations
import json, hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
INTEL=ROOT/"data/intelligence"
ATTR=LIVE/"nic_attribution_intelligence_7.json"
PORTFOLIO=LIVE/"nic_adaptive_content_portfolio_8.json"
CRAFT=LIVE/"nic_content_craft_9.json"
RECENT=LIVE/"publication_log.jsonl"
OUT=LIVE/"nic_content_master_10.json"
REPORT=INTEL/"nic_content_master_10_report.json"

KEYS=("content_lane","craft_pattern","hook_type","visual_type","reader_payoff_type","content_format")

def load(path):
    try:
        x=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def recent_count():
    if not RECENT.exists(): return 0
    return len(RECENT.read_text(encoding="utf-8",errors="ignore").splitlines()[-100:])

def main():
    attribution=load(ATTR)
    portfolio=load(PORTFOLIO)
    craft=load(CRAFT)
    posts=[x for x in attribution.get("posts",[]) if isinstance(x,dict)]
    verified=[x for x in posts if x.get("outcome_state")=="VERIFIED_REWARD"]
    unknown=[x for x in posts if x.get("outcome_state")=="UNKNOWN"]
    explicit_zero=[x for x in posts if x.get("outcome_state")=="VERIFIED_NO_REWARD"]

    groups={k:defaultdict(lambda:{"observations":0,"verified_rewards":0,"verified_revenue_usdc":0.0,"unknown":0,"verified_no_reward":0}) for k in KEYS}
    for row in posts:
        for key in KEYS:
            value=str(row.get(key) or "").strip()
            if not value: continue
            g=groups[key][value]
            g["observations"]+=1
            state=row.get("outcome_state")
            if state=="VERIFIED_REWARD":
                g["verified_rewards"]+=1
                g["verified_revenue_usdc"]+=float(row.get("verified_reward_usdc") or 0)
            elif state=="VERIFIED_NO_REWARD":
                g["verified_no_reward"]+=1
            else:
                g["unknown"]+=1

    priors={}
    for key, bucket in groups.items():
        items=[]
        for value,g in bucket.items():
            # Positive evidence is deliberately bounded and requires an explicit
            # verified reward. UNKNOWN never subtracts from a pattern.
            reward_rate=(g["verified_rewards"]/g["observations"]) if g["observations"] else 0.0
            evidence_strength=min(1.0, g["verified_rewards"]/3.0)
            score=0.50 + 0.25*evidence_strength + 0.25*min(1.0,reward_rate)
            if g["verified_rewards"]==0:
                score=0.50
            items.append({
                "value":value,
                **g,
                "verified_reward_rate":round(reward_rate,6),
                "bounded_preference":round(score,6),
                "learning_state":"VERIFIED_SIGNAL" if g["verified_rewards"] else "UNKNOWN_OR_INSUFFICIENT",
            })
        priors[key]=sorted(items,key=lambda x:(x["bounded_preference"],x["value"]),reverse=True)[:50]

    # Choose only a bounded tie-breaker: verified observations may add a small
    # preference; all patterns retain exploration eligibility.
    craft_pattern=str(craft.get("archetype") or craft.get("hook_type") or "")
    lane=str(craft.get("lane") or "")
    recommendations=[]
    for key in KEYS:
        candidates=priors[key]
        if not candidates: continue
        top=candidates[0]
        recommendations.append({
            "dimension":key,
            "preferred_value":top["value"],
            "bounded_preference":top["bounded_preference"],
            "evidence_state":top["learning_state"],
            "reason":"verified outcome evidence" if top["verified_rewards"] else "exploration; insufficient verified reward evidence",
        })

    master_id="master10-"+hashlib.sha256(
        json.dumps({"verified":len(verified),"unknown":len(unknown),"zero":len(explicit_zero),"recent":recent_count()},sort_keys=True).encode()
    ).hexdigest()[:16]

    state={
        "version":"10.0","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),
        "master_id":master_id,
        "purpose":"bounded editorial learning from explicit verified publication outcomes",
        "evidence_policy":{
            "verified_reward_required_for_positive_learning":True,
            "unknown_is_neutral":True,
            "verified_no_reward_is_distinct_from_unknown":True,
            "views_likes_comments_are_not_revenue":True,
            "prediction_outcomes_are_not_revenue":True,
            "no_income_guarantee":True,
            "no_publish_permission":True,
            "private_reasoning_never_exposed":True,
        },
        "observation_summary":{
            "attributed_posts":len(posts),
            "verified_reward_posts":len(verified),
            "verified_no_reward_posts":len(explicit_zero),
            "unknown_posts":len(unknown),
            "verified_revenue_usdc":round(sum(float(x.get("verified_reward_usdc") or 0) for x in verified),8),
        },
        "learned_dimensions":priors,
        "bounded_recommendations":recommendations,
        "current_craft_context":{
            "craft_id":craft.get("craft_id"),
            "lane":lane,
            "pattern":craft_pattern,
            "portfolio_primary_lane":portfolio.get("next_cycle",{}).get("primary_lane"),
        },
        "selection_rule":"Use this contract only as a bounded tie-breaker after Signal-First, Story Discovery and Content Craft. Preserve exploration and never convert UNKNOWN into a penalty.",
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"10.0","status":"READY","master_id":master_id,**state["observation_summary"],"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","version":"10.0","master_id":master_id,"verified_reward_posts":len(verified),"unknown_posts":len(unknown)}))

if __name__=="__main__":
    main()
