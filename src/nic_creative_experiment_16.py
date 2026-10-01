"""NIC 16 — Creative Experimentation Engine.

Creates bounded, durable creative experiments with exact lineage. One active
experiment is held across multiple publications so treatment/control samples can
actually accumulate. Outcomes are descriptive until both arms have enough mature
observations; verified rewards are the only monetization signal.
"""
from __future__ import annotations
import hashlib, json, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; AN=ROOT/"analytics"; INTEL=ROOT/"data/intelligence"
LEARNING=LIVE/"nic_creative_learning_15.json"
OUT=LIVE/"nic_creative_experiment_16.json"
REPORT=INTEL/"nic_creative_experiment_16_report.json"
REGISTRY=AN/"nic_creative_experiment_16_registry.json"
ATTR=AN/"publication_attribution.jsonl"
OUTCOMES=LIVE/"nic_post_publication_outcome_14.json"

VARIABLES={
 "hook_type":["decision_point","data_contradiction","verified_event","surprising_relationship","failure_test","thesis_result"],
 "story_structure":["thesis_evidence_falsifier","surprise_mechanism_test","event_transmission_confirmation","consensus_contrary_falsifier","before_after_changed_view","data_limitation_takeaway"],
 "visual_type":["decision_map","relationship_chart","event_to_market_map","failure_map","before_after","scenario_tree","relative_strength","historical_analogue"],
 "reader_payoff_type":["confirmation_rule","data_relationship","mechanism_explanation","falsification_test","what_changed","next_test","tradeoff_framework"],
}
SAFE_FALLBACKS={
 "hook_type":("decision_point","data_contradiction"),
 "story_structure":("thesis_evidence_falsifier","surprise_mechanism_test"),
 "visual_type":("decision_map","relationship_chart"),
 "reader_payoff_type":("confirmation_rule","data_relationship"),
}
MIN_MATURE_ARM=2
MAX_EXPERIMENT_POSTS=12

def load(path, default):
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, type(default)) else default
    except Exception:return default

def rows(path):
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def clean(v): return str(v or "").strip()

def post_id(x):
    raw=clean(x.get("canonical_post_id") or x.get("post_id"))
    if "/square/post/" in raw: raw=raw.split("/square/post/",1)[1].split("?",1)[0]
    return raw

def arm_for(experiment_id, post_key):
    h=int(hashlib.sha256(f"{experiment_id}:{post_key}".encode()).hexdigest()[:8],16)
    return "treatment" if h%2 else "control"

def choose_experiment(reg):
    active=reg.get("active_experiment")
    if isinstance(active,dict) and active.get("status")=="ACTIVE":
        return active
    digest=hashlib.sha256(datetime.now(timezone.utc).strftime("%Y-%m-%d").encode()).hexdigest()
    variable=list(VARIABLES)[int(digest[:4],16)%len(VARIABLES)]
    control,treatment=SAFE_FALLBACKS[variable]
    return {
      "experiment_id":"nic16-"+hashlib.sha256(f"{variable}:{datetime.now(timezone.utc).strftime('%Y%m%d')}".encode()).hexdigest()[:14],
      "version":"16.0","status":"ACTIVE","primary_variable":variable,
      "control_value":control,"treatment_value":treatment,
      "created_at":datetime.now(timezone.utc).isoformat(),
      "posts_assigned":0,"mature_control":0,"mature_treatment":0,
    }

def evaluate(active, attr, outcomes):
    by_id={post_id(x):x for x in outcomes if post_id(x)}
    arms=defaultdict(list)
    for x in attr:
        if clean(x.get("experiment_id"))!=clean(active.get("experiment_id")): continue
        pid=post_id(x)
        if not pid: continue
        arm=clean(x.get("experiment_treatment") or "")
        arm="treatment" if arm==clean(active.get("treatment_value")) else ("control" if arm==clean(active.get("control_value")) else "")
        if not arm: continue
        o=by_id.get(pid,{})
        state=clean(o.get("outcome_state"))
        if state in {"OPEN_OBSERVATION",""}: continue
        arms[arm].append({
          "post_id":pid,"outcome_state":state,
          "reward_usdc":float(o.get("verified_reward_usdc") or 0),
          "reward_verified":state=="VERIFIED_REWARD",
          "metrics":o.get("explicit_audience_metrics") or {},
        })
    summary={}
    for arm,items in arms.items():
        rewards=sum(1 for x in items if x["reward_verified"])
        amount=sum(x["reward_usdc"] for x in items)
        views=sum(float(x["metrics"].get("views") or 0) for x in items)
        likes=sum(float(x["metrics"].get("likes") or 0) for x in items)
        replies=sum(float(x["metrics"].get("replies") or 0) for x in items)
        summary[arm]={"mature_posts":len(items),"verified_reward_posts":rewards,
                      "verified_reward_usdc":round(amount,8),
                      "explicit_views":views,"explicit_likes":likes,"explicit_replies":replies}
    return summary

def main():
    now=datetime.now(timezone.utc)
    reg=load(REGISTRY,{"version":"16.0","active_experiment":None,"history":[]})
    active=choose_experiment(reg)
    attr=rows(ATTR); outcomes=(load(OUTCOMES,{"outcomes":[]}).get("outcomes") or [])
    # Assignment is deterministic per exact run; the same run cannot silently
    # switch arms on retry.
    run_key=clean(__import__("os").environ.get("GITHUB_RUN_ID")) or now.strftime("%Y%m%d%H%M")
    arm=arm_for(active["experiment_id"],run_key)
    selected=active["treatment_value"] if arm=="treatment" else active["control_value"]
    evaluation=evaluate(active,attr,outcomes)
    active["mature_control"]=evaluation.get("control",{}).get("mature_posts",0)
    active["mature_treatment"]=evaluation.get("treatment",{}).get("mature_posts",0)
    active["posts_assigned"]=sum(1 for x in attr if clean(x.get("experiment_id"))==clean(active["experiment_id"]))
    mature_both=active["mature_control"]>=MIN_MATURE_ARM and active["mature_treatment"]>=MIN_MATURE_ARM
    decision="CONTINUE_COLLECTION"
    if mature_both or active["posts_assigned"]>=MAX_EXPERIMENT_POSTS:
        decision="EVALUATE_AND_ROTATE"
        active["status"]="COMPLETED"
        reg.setdefault("history",[]).append({"experiment":active,"evaluation":evaluation,"completed_at":now.isoformat()})
        active=choose_experiment({**reg,"active_experiment":None})
        arm=arm_for(active["experiment_id"],run_key)
        selected=active["treatment_value"] if arm=="treatment" else active["control_value"]
        decision="START_NEXT_EXPERIMENT"
    result={
      "version":"16.0","status":"READY","generated_at":now.isoformat(),
      "experiment_id":active["experiment_id"],"primary_variable":active["primary_variable"],
      "assignment":{"run_key":run_key,"arm":arm,"control_value":active["control_value"],"treatment_value":active["treatment_value"],
                    "selected_value":selected,"assignment_policy":"deterministic_hash_exact_run_key"},
      "directive":{"force_variable":active["primary_variable"],"selected_value":selected,
                   "control_value":active["control_value"],"treatment_value":active["treatment_value"],
                   "visible_change_required":True,"preserve_factual_evidence":True,
                   "do_not_change_asset_for_experiment":True},
      "evaluation":evaluation,"decision":decision,
      "policy":{"bounded_variation_only":True,"exact_post_id_lineage":True,
                "mature_observations_only":True,"verified_reward_only_for_monetization":True,
                "unknown_is_neutral":True,"no_causal_claim_before_both_arms_mature":True,
                "no_guaranteed_revenue":True,"no_hidden_reasoning":True},
      "history_count":len(reg.get("history") or []),
    }
    # Persist active experiment and expose the selected arm to the existing
    # monetization contract, which the publisher already records by post ID.
    reg["version"]="16.0"; reg["active_experiment"]=active; reg["updated_at"]=now.isoformat()
    LIVE.mkdir(parents=True,exist_ok=True); AN.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    REGISTRY.write_text(json.dumps(reg,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    contract_path=LIVE/"nic_monetization_contract.json"
    contract=load(contract_path,{})
    contract.update({"experiment_id":active["experiment_id"],"experiment_variable":active["primary_variable"],
                     "experiment_treatment":selected,"experiment_arm":arm,"experiment_source":"NIC_16_CREATIVE_EXPERIMENTATION",
                     "experiment_control_value":active["control_value"],"experiment_treatment_value":active["treatment_value"]})
    if contract: contract_path.write_text(json.dumps(contract,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"16.0","status":"READY","experiment_id":active["experiment_id"],
      "primary_variable":active["primary_variable"],"assignment":result["assignment"],"evaluation":evaluation,
      "decision":decision,"output":"data/live/nic_creative_experiment_16.json"},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","experiment_id":active["experiment_id"],"variable":active["primary_variable"],
                      "arm":arm,"selected_value":selected,"decision":decision},ensure_ascii=False))

if __name__=="__main__": main()
