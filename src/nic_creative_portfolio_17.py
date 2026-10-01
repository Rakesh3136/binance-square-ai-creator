"""NIC 17 — Creative Portfolio Allocator.

Builds a rolling publication portfolio instead of optimizing one post at a time.
Uses mature explicit evidence only for exploitation; preserves exploration,
repetition caps, cross-dimensional diversity, and exact plan/slot lineage.
"""
from __future__ import annotations
import hashlib, json, os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; AN=ROOT/"analytics"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_creative_portfolio_17.json"
REPORT=INTEL/"nic_creative_portfolio_17_report.json"
REGISTRY=AN/"nic_creative_portfolio_17_registry.json"
OUTCOMES=LIVE/"nic_post_publication_outcome_14.json"
LEARNING=LIVE/"nic_creative_learning_15.json"
EXPERIMENT=LIVE/"nic_creative_experiment_16.json"
PUBLOG=AN/"publication_log.jsonl"
ATTR=AN/"publication_attribution.jsonl"

LANES=["market_setup","data_investigation","breaking_news","world_macro","research_lesson","education","contrarian","follow_up","outcome_accountability","weekly_synthesis"]
FORMATS=["decision_chart","data_story","news_analysis","mechanism_explainer","scenario_map","contrarian_thesis","follow_up","research_note","educational_teardown","portfolio_synthesis"]
VISUALS=["decision_map","relationship_chart","event_to_market_map","failure_map","before_after","scenario_tree","relative_strength","historical_analogue","volume_structure","correlation_map"]
HOOKS=["decision_point","data_contradiction","verified_event","surprising_relationship","failure_test","thesis_result"]
PAYOFFS=["confirmation_rule","data_relationship","mechanism_explanation","falsification_test","what_changed","next_test","tradeoff_framework"]
N=6
RECENT_WINDOW=12
MAX_DIM_REPEAT=3

def load(path, default):
    try:
        x=json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x,type(default)) else default
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

def mature_outcomes():
    data=load(OUTCOMES,{"outcomes":[]})
    return [x for x in (data.get("outcomes") or []) if clean(x.get("outcome_state")) in {"VERIFIED_REWARD","CLOSED_NO_VERIFIED_REWARD"}]

def reward_patterns():
    learning=load(LEARNING,{})
    patterns=learning.get("promoted_patterns") or learning.get("patterns") or []
    out=[]
    for p in patterns:
        if isinstance(p,dict) and int(p.get("verified_reward_count") or p.get("reward_count") or 0)>0:
            out.append(p)
    return out

def recent_publications():
    return rows(PUBLOG)[-RECENT_WINDOW:]

def dimension_counts(recent,key):
    return Counter(clean(x.get(key)) for x in recent if clean(x.get(key)))

def digest(text): return hashlib.sha256(text.encode()).hexdigest()

def choose_value(values, recent, key, slot_seed, preferred=None):
    counts=Counter(clean(x.get(key)) for x in recent if clean(x.get(key)))
    candidates=list(dict.fromkeys(values))
    if preferred and preferred in candidates and counts[preferred] < MAX_DIM_REPEAT:
        candidates=[preferred]+[x for x in candidates if x!=preferred]
    candidates.sort(key=lambda v:(counts[v]>=MAX_DIM_REPEAT, counts[v], digest(f"{slot_seed}:{key}:{v}")[:12]))
    return candidates[0]

def build_slots(recent, promoted, exp):
    slots=[]
    # Exploration is guaranteed: half the portfolio starts from creative
    # combinations absent from the recent window.
    for i in range(N):
        seed=f"{PLAN_ID}:{i}"
        pref=promoted[i % len(promoted)] if promoted else {}
        expdir=exp.get("directive") or {}
        hook=choose_value(HOOKS,recent,"hook_type",seed,pref.get("hook_type"))
        lane=choose_value(LANES,recent,"content_lane",seed,pref.get("content_lane") or pref.get("lane"))
        fmt=choose_value(FORMATS,recent,"content_format",seed,pref.get("content_format") or pref.get("format"))
        visual=choose_value(VISUALS,recent,"visual_type",seed,expdir.get("selected_value") if expdir.get("force_variable")=="visual_type" else pref.get("visual_type"))
        payoff=choose_value(PAYOFFS,recent,"reader_payoff_type",seed,pref.get("reader_payoff_type"))
        # NIC16 is a slot constraint, not a license to change the asset.
        if i==0 and expdir.get("force_variable") in {"hook_type","visual_type","reader_payoff_type"}:
            key=expdir["force_variable"]; val=clean(expdir.get("selected_value"))
            if val in globals().get({"hook_type":"HOOKS","visual_type":"VISUALS","reader_payoff_type":"PAYOFFS"}[key],[]):
                if key=="hook_type": hook=val
                elif key=="visual_type": visual=val
                else: payoff=val
        slots.append({
            "slot_id":f"{PLAN_ID}-S{i+1}",
            "portfolio_strategy":"explore" if i<N//2 else "bounded_exploitation",
            "content_lane":lane,"content_format":fmt,"hook_type":hook,
            "visual_type":visual,"reader_payoff_type":payoff,
            "asset_policy":"authoritative_asset_only",
            "experiment_id":clean(exp.get("experiment_id")),
            "experiment_variable":clean(exp.get("primary_variable")),
            "experiment_treatment":clean((exp.get("assignment") or {}).get("selected_value")),
            "lineage":{"portfolio_plan_id":PLAN_ID,"slot_id":f"{PLAN_ID}-S{i+1}"}
        })
    return slots

def main():
    global PLAN_ID
    now=datetime.now(timezone.utc)
    recent=recent_publications()
    promoted=reward_patterns()
    exp=load(EXPERIMENT,{})
    previous=load(REGISTRY,{"plans":[]})
    cycle=os.getenv("GITHUB_RUN_ID") or now.strftime("%Y%m%d%H%M")
    PLAN_ID="nic17-"+digest(cycle)[:14]
    slots=build_slots(recent,promoted,exp)
    # Portfolio-level collision repair: each slot must differ in at least two
    # visible creative dimensions from its immediate predecessor.
    for i in range(1,len(slots)):
        same=sum(slots[i][k]==slots[i-1][k] for k in ("content_lane","content_format","hook_type","visual_type","reader_payoff_type"))
        if same>=4:
            slots[i]["visual_type"]=choose_value(VISUALS,recent,"visual_type",f"{PLAN_ID}:repair:{i}",None)
            slots[i]["hook_type"]=choose_value(HOOKS,recent,"hook_type",f"{PLAN_ID}:repair-hook:{i}",None)
    result={
      "version":"17.0","status":"READY","generated_at":now.isoformat(),
      "portfolio_plan_id":PLAN_ID,"portfolio_size":len(slots),
      "slots":slots,
      "allocator_policy":{
        "exploration_floor":0.5,"recent_window":RECENT_WINDOW,
        "max_dimension_repeat":MAX_DIM_REPEAT,
        "mature_evidence_only_for_exploitation":True,
        "verified_reward_only_for_monetization":True,
        "unknown_is_neutral":True,"exact_post_id_lineage":True,
        "no_revenue_guarantee":True,"no_hidden_reasoning":True,
        "asset_changes_by_portfolio":False
      },
      "evidence":{"mature_outcomes":len(mature_outcomes()),"promoted_reward_patterns":len(promoted),
                  "recent_publications":len(recent),"nic16_experiment_id":clean(exp.get("experiment_id"))}
    }
    previous.setdefault("plans",[]).append({"portfolio_plan_id":PLAN_ID,"created_at":now.isoformat(),"slot_ids":[x["slot_id"] for x in slots]})
    previous["plans"]=previous["plans"][-30:]; previous["active_plan_id"]=PLAN_ID; previous["updated_at"]=now.isoformat()
    for p in (LIVE,AN,INTEL): p.mkdir(parents=True,exist_ok=True)
    REGISTRY.write_text(json.dumps(previous,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"17.0","status":"READY","portfolio_plan_id":PLAN_ID,
        "slots":slots,"evidence":result["evidence"],"policy":result["allocator_policy"]},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Feed the active slot into the existing generation contract. This is
    # intentionally deterministic and durable for the current run.
    idx=int(digest(cycle)[:8],16)%len(slots)
    selected=slots[idx]
    contract_path=LIVE/"nic_monetization_contract.json"
    contract=load(contract_path,{})
    contract.update({"portfolio_plan_id":PLAN_ID,"portfolio_slot_id":selected["slot_id"],
        "portfolio_strategy":selected["portfolio_strategy"],"portfolio_lane":selected["content_lane"],
        "portfolio_format":selected["content_format"],"portfolio_hook_type":selected["hook_type"],
        "portfolio_visual_type":selected["visual_type"],"portfolio_reader_payoff_type":selected["reader_payoff_type"],
        "portfolio_source":"NIC_17_CREATIVE_PORTFOLIO_ALLOCATOR"})
    if contract: contract_path.write_text(json.dumps(contract,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    result["selected_slot"]=selected
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","portfolio_plan_id":PLAN_ID,"selected_slot":selected["slot_id"],
                      "lane":selected["content_lane"],"format":selected["content_format"],"visual":selected["visual_type"]}))
if __name__=="__main__": main()
