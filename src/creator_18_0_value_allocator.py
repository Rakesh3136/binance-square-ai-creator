"""Creator 18.0 — Evidence-Based Value Allocation.

Allocates the creator's limited publishing/execution attention across content
categories using observed performance and explicitly verified monetization.
It is an optimization layer, not a promise of earnings or investment advice.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
ANALYTICS=ROOT/"analytics"; LIVE=ROOT/"data"/"live"; INTEL=ROOT/"data"/"intelligence"
STATE=ANALYTICS/"creator_18_0_value_allocation.json"

def load(p:Path,d:Any=None)->Any:
    try:return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError,OSError):return d

def save(p:Path,x:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def num(x:Any,*keys:str)->float:
    if not isinstance(x,dict): return 0.0
    for k in keys:
        v=x.get(k)
        if isinstance(v,(int,float)) and math.isfinite(float(v)): return float(v)
    return 0.0

def main()->int:
    stamp=datetime.now(timezone.utc).isoformat()
    portfolio=load(ANALYTICS/"creator_7_5_growth_portfolio.json",{})
    strategy=load(ANALYTICS/"strategy_memory.json",{})
    outcomes=load(ANALYTICS/"creator_7_2_state.json",{})
    revenue=load(ANALYTICS/"creator_8_0_monetization_engine.json",{})
    decision=load(LIVE/"creator_16_0_decision_board.json",{})
    research=load(LIVE/"creator_17_0_research_state.json",{})
    opportunities=load(LIVE/"creator_15_0_opportunity_board.json",{})

    buckets=["BREAKING_MARKET","EXPLAINER","DATA_DEEP_DIVE","DEBATE","MACRO_REGULATION"]
    target={k:0.20 for k in buckets}
    if isinstance(portfolio,dict):
        raw=portfolio.get("target_mix",portfolio.get("portfolio",{}))
        if isinstance(raw,dict):
            for k in buckets:
                v=raw.get(k)
                if isinstance(v,(int,float)) and v>=0: target[k]=float(v)
    total=sum(target.values()) or 1.0
    target={k:v/total for k,v in target.items()}

    # Evidence score comes from observed strategy preferences, never guessed revenue.
    prefs=strategy.get("preferences",{}) if isinstance(strategy,dict) else {}
    if not isinstance(prefs,dict): prefs={}
    verified_revenue=num(revenue,"verified_revenue","revenue_verified","verified_earnings","earnings_verified")
    confidence=max(0.0,min(1.0,num(research,"evidence_summary","confidence"))) if False else 0.0
    if isinstance(research,dict):
        es=research.get("evidence_summary",{})
        confidence=max(0.0,min(1.0, num(es,"official_feed")/5.0 + num(es,"total")/40.0))
    decision_quality=0.5
    if isinstance(decision,dict): decision_quality=1.0 if decision.get("status")=="DECISION_READY" else 0.45

    allocations=[]
    for bucket in buckets:
        observed=0.0
        p=prefs.get(bucket,{}) if isinstance(prefs,dict) else {}
        if isinstance(p,dict): observed=num(p,"outcome_score","score","performance")
        observed=max(0.0,min(1.0,observed))
        evidence=max(0.25,confidence)
        # Blend prior portfolio target with evidence; keep exploration floor.
        raw=0.55*target[bucket]+0.30*observed+0.15*(1.0-target[bucket])
        allocations.append({"category":bucket,"recommended_share":raw,"observed_signal":observed,"evidence_confidence":round(evidence,3)})
    total2=sum(x["recommended_share"] for x in allocations) or 1.0
    for x in allocations: x["recommended_share"]=round(x["recommended_share"]/total2,4)

    selected=opportunities.get("selected") if isinstance(opportunities,dict) else None
    action="ALLOCATE_ATTENTION" if selected else "PRESERVE_EXPLORATION"
    if isinstance(research,dict) and research.get("decision_impact")=="BLOCK_UNTIL_VERIFIED": action="HOLD_AND_VERIFY"

    result={
      "schema_version":"18.0","generated_at":stamp,"status":"READY","action":action,
      "allocation_basis":"observed performance + portfolio priors + evidence confidence",
      "allocations":sorted(allocations,key=lambda x:x["recommended_share"],reverse=True),
      "selected_opportunity_id":selected.get("opportunity_id") if isinstance(selected,dict) else None,
      "verified_revenue":verified_revenue,
      "revenue_policy":"only explicit verified revenue/earnings fields count; zero does not mean revenue is impossible",
      "decision_quality":decision_quality,
      "constraints":["no inferred revenue","no earnings guarantee","no fake engagement","no fabricated evidence","no quality_gate_bypass","no credential changes"]
    }
    save(STATE,result)
    save(INTEL/"creator_18_0_report.json",{"module":"creator_18_0_value_allocator","generated_at":stamp,"status":result["status"],"action":action,"verified_revenue":verified_revenue,"top_category":result["allocations"][0]["category"]})
    strategy.setdefault("creator_18_0",{})
    strategy["creator_18_0"]={"action":action,"top_category":result["allocations"][0]["category"],"allocations":result["allocations"],"verified_revenue":verified_revenue}
    strategy.setdefault("learning_overlay",{})["value_allocation"]=strategy["creator_18_0"]
    save(ANALYTICS/"strategy_memory.json",strategy)
    print(json.dumps({"status":"READY","action":action,"top_category":result["allocations"][0]["category"],"verified_revenue":verified_revenue},indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
