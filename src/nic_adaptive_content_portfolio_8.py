"""NIC Adaptive Content Portfolio 8.0 — bounded portfolio allocation.

Allocates future editorial exploration across story lanes using verified
attribution evidence when available, while preserving exploration and never
turning missing telemetry into a negative signal.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
INTEL=ROOT/"data/intelligence"
ATTR=LIVE/"nic_attribution_intelligence_7.json"
OUT=LIVE/"nic_adaptive_content_portfolio_8.json"
REPORT=INTEL/"nic_adaptive_content_portfolio_8_report.json"

LANES=[
    "market_setup","data_investigation","breaking_news","world_macro",
    "research_lesson","education","contrarian_thesis","follow_up",
    "outcome_accountability","weekly_synthesis","nic_learning_note",
]

def load(path):
    try:
        x=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def main():
    attribution=load(ATTR)
    priors={str(x.get("lane") or ""):x for x in attribution.get("learning",{}).get("lane_priors",[]) or []}
    total_verified=sum(int(x.get("verified_rewards") or 0) for x in priors.values())
    allocations=[]
    # Default is deliberately exploration-heavy. Verified rewards can tilt,
    # but never monopolize the portfolio.
    base=1.0/max(len(LANES),1)
    for lane in LANES:
        p=priors.get(lane,{})
        verified=int(p.get("verified_rewards") or 0)
        revenue=float(p.get("verified_revenue_usdc") or 0)
        if verified>0:
            evidence_bonus=min(0.08,0.02*verified)
            revenue_bonus=min(0.04,revenue/1000.0)
        else:
            evidence_bonus=0.0; revenue_bonus=0.0
        allocation=base+evidence_bonus+revenue_bonus
        allocations.append({"lane":lane,"allocation_score":round(allocation,6),
                             "verified_reward_observations":verified,
                             "verified_revenue_usdc":round(revenue,8),
                             "evidence_state":"VERIFIED_SIGNAL" if verified else "UNKNOWN_OR_INSUFFICIENT"})
    total=sum(x["allocation_score"] for x in allocations)
    for x in allocations:
        x["target_share"]=round(x["allocation_score"]/total,6)
    allocations.sort(key=lambda x:(x["target_share"],x["lane"]),reverse=True)
    state={
      "version":"8.0",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "status":"READY",
      "policy":{
        "exploration_floor_per_lane":round(base/total,6),
        "verified_signal_only_for_positive_adjustment":True,
        "unknown_is_not_negative":True,
        "no_revenue_inference":True,
        "no_guaranteed_income":True,
        "market_signal_and_editorial_quality_remain_authoritative":True,
        "one_primary_variable_per_experiment":True,
        "portfolio_is_allocation_guidance_not_publish_permission":True,
      },
      "verified_evidence":{
        "total_reward_observations":total_verified,
        "source":"nic_attribution_intelligence_7",
      },
      "allocations":allocations,
      "selection_rule":"Signal-First chooses the opportunity; portfolio allocation only determines which supported story lane receives exploration priority.",
      "next_cycle":{
        "primary_lane":allocations[0]["lane"],
        "exploration_lanes":[x["lane"] for x in allocations[1:4]],
        "do_not_repeat_without_new_evidence":[],
      },
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"8.0","status":"READY","primary_lane":state["next_cycle"]["primary_lane"],"total_reward_observations":total_verified,"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","primary_lane":state["next_cycle"]["primary_lane"],"total_reward_observations":total_verified}))
if __name__=="__main__":
    main()
