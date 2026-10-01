"""NIC 15 — Durable Creative Learning Memory.

Converts mature, explicit outcome evidence into bounded reusable preferences.
It never treats unknown data as failure, never assigns unattributed rewards, and
requires repeated evidence before promoting a pattern.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_creative_learning_15.json"; REPORT=INTEL/"nic_creative_learning_15_report.json"
SOURCE=LIVE/"nic_post_publication_outcome_14.json"
MIN_REPEATED=2

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    now=datetime.now(timezone.utc)
    source=load(SOURCE)
    outcomes=source.get("outcomes") or []
    groups=defaultdict(lambda:{"n":0,"reward_n":0,"reward_usdc":0.0,"closed":0,"open":0})
    for x in outcomes:
        state=x.get("outcome_state")
        if state=="OPEN_OBSERVATION": continue
        lane=x.get("content_lane"); fmt=x.get("content_format"); visual=x.get("visual_type")
        for dimension,value in (("lane",lane),("format",fmt),("visual",visual)):
            if not value: continue
            g=groups[(dimension,str(value))]
            g["n"]+=1
            if state=="VERIFIED_REWARD":
                g["reward_n"]+=1
                g["reward_usdc"]+=float(x.get("verified_reward_usdc") or 0)
            if state=="CLOSED_NO_VERIFIED_REWARD": g["closed"]+=1

    promoted=[]; observed=[]
    for (dimension,value),g in groups.items():
        rate=(g["reward_n"]/g["n"]) if g["n"] else 0.0
        rec={"dimension":dimension,"value":value,**g,"reward_rate":round(rate,4)}
        observed.append(rec)
        if g["n"]>=MIN_REPEATED and g["reward_n"]>=1:
            promoted.append({**rec,"status":"EVIDENCE_SUPPORTED","promotion_rule":"at_least_2_mature_observations_and_1_verified_reward"})
    promoted.sort(key=lambda x:(x["reward_n"],x["reward_usdc"],x["n"]),reverse=True)
    result={
        "version":"15.0","status":"READY","generated_at":now.isoformat(),
        "policy":{"mature_observations_only":True,"minimum_repeated_observations":MIN_REPEATED,
                  "verified_reward_required_for_promotion":True,"unknown_is_neutral":True,
                  "no_causal_claim_from_single_post":True,"unattributed_rewards_not_assigned":True,
                  "preferences_are_bounded_guidance_not_guarantees":True},
        "summary":{"mature_outcomes":len([x for x in outcomes if x.get("outcome_state")!="OPEN_OBSERVATION"]),
                   "observed_patterns":len(observed),"promoted_patterns":len(promoted)},
        "promoted_patterns":promoted[:30],"observed_patterns":observed[:100],
        "next_cycle_guidance":{
            "use_promoted_patterns_as_soft_preferences":True,
            "keep_exploration_alive":True,
            "never_repeat_a_pattern_only_because_it_has_one_reward":True,
            "unknown_data_does_not_penalize_creative_families":True
        }
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"15.0","status":"READY","summary":result["summary"],
                                  "promoted_patterns":promoted[:10],"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY",**result["summary"]}))
if __name__=="__main__": main()
