"""Measure creator experiments using verified post and reward evidence only."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
OUT=LIVE/"nic_creator_experiment_scorecard.json"
PUBLICATION_LOG=LIVE/"publication_log.json"
REWARD_LOG=LIVE/"write_to_earn_attribution.json"

def read(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError,json.JSONDecodeError):
        return []
def rows(value):
    if isinstance(value,list): return [x for x in value if isinstance(x,dict)]
    if isinstance(value,dict):
        for key in ("records","publications","events","rows","attributions"):
            if isinstance(value.get(key),list): return [x for x in value[key] if isinstance(x,dict)]
    return []
def verified_post(row):
    status=str(row.get("status") or row.get("publication_status") or "").upper()
    post_id=row.get("canonical_post_id") or row.get("post_id")
    proof=row.get("proof") or row.get("publication_proof") or row.get("proof_status")
    return bool(post_id) and (status in {"PUBLISHED_VERIFIED_BY_API_RESPONSE","CONFIRMED_PUBLISHED","VERIFIED_PUBLISHED"} or proof in {"CONFIRMED_PUBLISHED","PUBLISHED_VERIFIED_BY_API_RESPONSE",True})
def positive_number(value):
    try:
        n=float(value)
        return n if n>=0 else None
    except (TypeError,ValueError): return None
def build_scorecard(publications,rewards):
    reward_by_id={}
    for reward in rewards:
        post_id=str(reward.get("canonical_post_id") or reward.get("post_id") or "")
        if not post_id or str(reward.get("verification_status") or reward.get("status") or "").upper() not in {"VERIFIED","CONFIRMED","PAID","REWARDED"}:
            continue
        amount=positive_number(reward.get("reward_usdc") if reward.get("reward_usdc") is not None else reward.get("amount_usdc"))
        if amount is not None: reward_by_id[post_id]=reward_by_id.get(post_id,0.0)+amount
    eligible=[]
    rejected=0
    for p in publications:
        if not verified_post(p):
            rejected+=1; continue
        pid=str(p.get("canonical_post_id") or p.get("post_id"))
        fmt=str(p.get("format") or p.get("content_format") or p.get("editorial_format") or "UNCLASSIFIED").upper()
        views=positive_number(p.get("views"))
        engagements=positive_number(p.get("engagements"))
        eligible.append({"post_id":pid,"format":fmt,"published_at":p.get("published_at") or p.get("timestamp"),"views":views,"engagements":engagements,"verified_reward_usdc":round(reward_by_id.get(pid,0.0),8),"revenue_verified":pid in reward_by_id})
    groups={}
    for p in eligible:
        g=groups.setdefault(p["format"],{"verified_posts":0,"posts_with_views":0,"views":0.0,"posts_with_engagements":0,"engagements":0.0,"posts_with_verified_rewards":0,"verified_reward_usdc":0.0})
        g["verified_posts"]+=1
        if p["views"] is not None: g["posts_with_views"]+=1; g["views"]+=p["views"]
        if p["engagements"] is not None: g["posts_with_engagements"]+=1; g["engagements"]+=p["engagements"]
        if p["revenue_verified"]: g["posts_with_verified_rewards"]+=1
        g["verified_reward_usdc"]+=p["verified_reward_usdc"]
    for g in groups.values():
        g["views"]=round(g["views"],2); g["engagements"]=round(g["engagements"],2); g["verified_reward_usdc"]=round(g["verified_reward_usdc"],8)
        g["average_views_per_measured_post"]=round(g["views"]/g["posts_with_views"],2) if g["posts_with_views"] else None
        g["engagement_rate"]=round(g["engagements"]/g["views"],6) if g["views"] and g["posts_with_views"] and g["posts_with_engagements"] else None
    return {"schema":"NIC-CREATOR-EXPERIMENT-SCORECARD-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"MEASURED_WITH_VERIFIED_PUBLICATIONS" if eligible else "NO_VERIFIED_PUBLICATION_SAMPLE","verified_publications":len(eligible),"rejected_unverified_publication_rows":rejected,"format_groups":groups,"posts":eligible,"rules":{"views_are_not_revenue":True,"only_verified_publications_count":True,"only_explicit_verified_rewards_count_as_revenue":True,"no_format_winner_declared_without_sufficient_sample":True,"minimum_posts_before_comparison":10},"limitations":["This scorecard measures available reach, engagement and verified rewards; it does not prove causation.","Missing metrics remain null and are never imputed.","Format performance must be compared across similar time windows and audience exposure."]}
def main():
    pubs=rows(read(PUBLICATION_LOG)); rewards=rows(read(REWARD_LOG))
    result=build_scorecard(pubs,rewards)
    LIVE.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"verified_publications":result["verified_publications"],"rejected_unverified_publication_rows":result["rejected_unverified_publication_rows"],"formats":list(result["format_groups"])},indent=2))
if __name__=="__main__": main()
