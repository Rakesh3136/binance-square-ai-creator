"""NIC Revenue Pattern Lab — evidence-first Write-to-Earn experiment planner.

It compares verified monetization observations with publication metadata and
creates bounded next experiments. It never invents attribution or revenue.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
try:
    from src.nic_reward_evidence import canonical_post_id, is_verified_reward_event, reward_event_rejection_reasons
except ModuleNotFoundError:
    from nic_reward_evidence import canonical_post_id, is_verified_reward_event, reward_event_rejection_reasons
try:
    from src.nic_owner_reported_rewards import load_owner_reported_rewards
except ModuleNotFoundError:
    from nic_owner_reported_rewards import load_owner_reported_rewards
ROOT=Path(__file__).resolve().parents[1]; AN=ROOT/"analytics"; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
ATTR=AN/"publication_attribution.jsonl"; PERF=AN/"square_performance.jsonl"; REWARD_EVENTS=AN/"wte_reward_events.jsonl"; OUT=LIVE/"nic_revenue_pattern_lab.json"; REPORT=INTEL/"nic_revenue_pattern_lab_report.json"
def rows(p):
    out=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict):out.append(x)
            except Exception: pass
    return out
def pid(x): return str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip().lower()
def num(x,*ks):
    # Square's collector stores metrics under a nested "metrics" object.
    # Keep direct-field support for older/imported rows, but fall back to the
    # canonical nested shape instead of silently recording every metric as 0.
    metrics=x.get("metrics") if isinstance(x.get("metrics"),dict) else {}
    for source in (x,metrics):
        for k in ks:
            if k not in source:
                continue
            try:
                value=float(source.get(k) or 0)
                if value == value and abs(value) != float("inf"): return value
            except Exception: pass
    return 0.0
def main():
    attrs={pid(x):x for x in rows(ATTR) if pid(x)}; perf={pid(x):x for x in rows(PERF) if pid(x)}; owner_rewards=load_owner_reported_rewards()
    raw_reward_events=rows(REWARD_EVENTS)
    # De-duplicate by stable event ID before aggregation. Repeated imports of the
    # same reward must never inflate revenue, while distinct verified payments
    # for one post must be summed rather than silently overwritten.
    valid_reward_events=[]
    seen_event_ids=set()
    duplicate_event_ids=0
    for event in raw_reward_events:
        if not is_verified_reward_event(event):
            continue
        event_id=str(event.get("event_id") or "").strip()
        if event_id in seen_event_ids:
            duplicate_event_ids+=1
            continue
        seen_event_ids.add(event_id)
        valid_reward_events.append(event)
    rewards=defaultdict(float)
    for event in valid_reward_events:
        rewards[canonical_post_id(event)]+=max(0,num(event,"reward_amount_usdc"))
    groups=defaultdict(lambda:{"posts":0,"views":0.0,"engagement":0.0,"verified_revenue":0.0,"verified_posts":0,"owner_reported_revenue":0.0,"owner_reported_posts":0})
    for p,a in attrs.items():
        fmt = a.get("content_format") or a.get("format") or a.get("portfolio_format")
        if not fmt and a.get("visual_attached") is True:
            fmt = "visual_attached"
        elif not fmt and a.get("visual_attached") is False:
            fmt = "text_only"
        hook = a.get("hook_type") or a.get("content_family") or a.get("portfolio_hook_type")
        k=(str(a.get("content_lane") or a.get("category") or a.get("portfolio_lane") or "unknown"),str(fmt or "unknown"),str(hook or "unknown"))
        g=groups[k]; g["posts"]+=1; r=perf.get(p,{})
        g["views"]+=num(r,"views","view_count","impressions"); g["engagement"]+=num(r,"likes","like_count")+2*num(r,"comments","reply_count")+3*num(r,"shares","share_count")
        reward=rewards.get(p,0.0)
        if reward > 0:
            g["verified_posts"]+=1; g["verified_revenue"]+=reward
        owner_reward=owner_rewards.get(p)
        if owner_reward:
            g["owner_reported_posts"]+=1; g["owner_reported_revenue"]+=owner_reward["amount_usdc"]

    observations=[]
    for (cat,fmt,fam),g in groups.items():
        observations.append({"category":cat,"content_lane":cat,"format":fmt,"content_format":fmt,"hook_type":fam,"content_family":fam,"posts":g["posts"],"views":round(g["views"],2),"engagement_per_1000_views":round(g["engagement"]*1000/max(g["views"],1),4),"verified_posts":g["verified_posts"],"verified_revenue":round(g["verified_revenue"],8),"owner_reported_posts":g["owner_reported_posts"],"owner_reported_revenue_usdc":round(g["owner_reported_revenue"],8),"owner_reported_evidence":"OWNER_REPORTED_NOT_INDEPENDENTLY_VERIFIED" if g["owner_reported_posts"] else None,"evidence":"OBSERVED_ONLY"})
    verified=[x for x in observations if x["verified_posts"]>0]
    plan=[]
    for x in sorted(observations,key=lambda z:(z["verified_revenue"],z["owner_reported_revenue_usdc"],z["engagement_per_1000_views"]),reverse=True)[:8]:
        plan.append({"test_family":x["content_family"],"format":x["format"],"hypothesis":"repeat only if fresh evidence supports the same content family","sample_rule":"minimum 3 comparable observations before changing policy","guardrail":"never infer revenue or causality from views alone"})
    state={"version":"2.1","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY" if verified else "COLLECTING_VERIFIED_REWARD_EVIDENCE","verified_observation_groups":len(verified),"reward_event_count":len(raw_reward_events),"accepted_verified_reward_events":len(valid_reward_events),"duplicate_reward_event_ids_ignored":duplicate_event_ids,"rejected_reward_events":len(raw_reward_events)-len(valid_reward_events)-duplicate_event_ids,"rejected_reward_event_diagnostics":[{"event_id":str(x.get("event_id") or "missing_event_id")[:120],"reasons":reward_event_rejection_reasons(x)} for x in raw_reward_events if not is_verified_reward_event(x)][:20],"observations":observations[:100],"next_experiments":plan,"verified_revenue_only":True,"owner_reported_reward_events_loaded":sum(x["event_count"] for x in owner_rewards.values()),"owner_reported_revenue_is_not_independently_verified":True,"owner_reported_reward_events_path":"analytics/wte_owner_reported_reward_events.jsonl","reward_requires_exact_post_id_and_hashed_timestamped_evidence":True,"unattributed_rewards_must_remain_unattributed":True}
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8");REPORT.write_text(json.dumps({"status":state["status"],"verified_groups":len(verified),"reward_event_count":len(raw_reward_events),"accepted_verified_reward_events":len(valid_reward_events),"duplicate_reward_event_ids_ignored":duplicate_event_ids,"rejected_reward_events":len(raw_reward_events)-len(valid_reward_events)-duplicate_event_ids,"rejection_reason_counts":{reason:sum(reason in reward_event_rejection_reasons(x) for x in raw_reward_events) for reason in sorted({r for x in raw_reward_events for r in reward_event_rejection_reasons(x)})},"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":state["status"],"verified_groups":len(verified),"accepted_verified_reward_events":len(valid_reward_events),"rejected_reward_events":len(raw_reward_events)-len(valid_reward_events),"rejection_reason_counts":{reason:sum(reason in reward_event_rejection_reasons(x) for x in raw_reward_events) for reason in sorted({r for x in raw_reward_events for r in reward_event_rejection_reasons(x)})},"observations":len(observations)}))
if __name__=="__main__":main()
