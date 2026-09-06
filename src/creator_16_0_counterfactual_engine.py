"""Creator 16.0 — Counterfactual Decision Engine.

Compares alternative next actions using evidence-backed expected-value estimates.
It does not claim causal certainty, invent outcomes, publish content, bypass gates,
or treat engagement as revenue.
"""
from __future__ import annotations
import hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
ANALYTICS=ROOT/"analytics"; LIVE=ROOT/"data"/"live"; INTEL=ROOT/"data"/"intelligence"
STATE=ANALYTICS/"creator_16_0_decision_memory.json"
BOARD=LIVE/"creator_16_0_decision_board.json"

def read(path:Path, default:Any)->Any:
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError,OSError):return default

def write(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def num(x:Any,d=0.0)->float:
    try:return float(x)
    except (TypeError,ValueError):return d

def clamp(x:float)->float:return max(0.0,min(1.0,x))
def now()->str:return datetime.now(timezone.utc).isoformat()
def did(x:Any)->str:return "cf16_"+hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:14]

def evidence_count(*objs:Any)->int:return sum(bool(o) for o in objs)

def main()->int:
    opp=read(LIVE/"creator_15_0_opportunity_board.json",{})
    world=read(ANALYTICS/"creator_14_0_world_model.json",{})
    brain=read(LIVE/"creator_9_0_brain_state.json",{})
    self_state=read(ANALYTICS/"creator_13_0_self_state.json",{})
    experiment=read(LIVE/"creator_12_0_active_experiment.json",{})
    strategy=read(ANALYTICS/"strategy_memory.json",{})
    outcomes=read(ANALYTICS/"creator_7_2_outcomes.jsonl",None)
    revenue=read(ANALYTICS/"creator_8_0_monetization_engine.json",{})
    memory=read(STATE,{"schema_version":"16.0","history":[]})
    history=memory.get("history",[]) if isinstance(memory,dict) else []

    selected=opp.get("selected_opportunity") if isinstance(opp,dict) else None
    ranked=opp.get("ranked_opportunities",[]) if isinstance(opp,dict) else []
    candidates=[]
    source_pool=ranked[:6]
    if not source_pool and selected: source_pool=[selected]

    verified_revenue=num(revenue.get("verified_revenue")) if isinstance(revenue,dict) else 0.0
    sample_count=num(strategy.get("sample_count")) if isinstance(strategy,dict) else 0.0
    data_conf=clamp((evidence_count(opp,world,brain,self_state,experiment,strategy,revenue))/7)
    if sample_count: data_conf=clamp(0.35+math.log10(1+sample_count)/2)

    for item in source_pool:
        dims=item.get("dimensions",{})
        base=clamp(num(item.get("score"),0.0))
        urgency=clamp(num(dims.get("urgency"),.5)); audience=clamp(num(dims.get("audience_fit"),.5))
        value=clamp(num(dims.get("expected_value"),.5)); confidence=clamp(num(dims.get("execution_confidence"),.5)); risk=clamp(num(dims.get("risk"),.5))
        # Counterfactual branches: publish now, test/iterate, or wait/research.
        for action,mult,extra_risk,delay_penalty in [
            ("PUBLISH_NOW",1.00,0.05,0.00),
            ("TEST_AND_ITERATE",0.90,0.02,0.08),
            ("RESEARCH_AND_WAIT",0.62,0.00,0.20),
        ]:
            probability=clamp(0.28+0.25*confidence+0.18*data_conf+0.12*audience-0.12*(risk+extra_risk))
            upside=clamp(0.35*base+0.25*value+0.18*audience+0.12*urgency+0.10*confidence)*mult
            downside=clamp(0.18*(risk+extra_risk)+0.10*(1-confidence)+delay_penalty)
            expected=round(probability*upside-(1-probability)*downside,6)
            uncertainty=round(1.0-data_conf*0.65-confidence*0.35,6)
            candidates.append({
                "decision_id":did([item.get("opportunity_id"),action]),
                "opportunity_id":item.get("opportunity_id"),"opportunity":item.get("title"),"action":action,
                "probability_of_favorable_outcome":round(probability,4),"estimated_upside":round(upside,4),
                "estimated_downside":round(downside,4),"expected_value":expected,"uncertainty":uncertainty,
                "evidence_basis":["creator_15_0_opportunity_board","creator_14_0_world_model","creator_9_0_brain_state","creator_12_0_active_experiment","strategy_memory"],
                "interpretation":"scenario estimate, not a causal or revenue forecast"
            })

    candidates.sort(key=lambda x:(x["expected_value"],-x["uncertainty"]),reverse=True)
    best=candidates[0] if candidates else None
    # Do not convert low-evidence speculation into an execution mandate.
    if not best or best["uncertainty"]>0.78:
        action="WAIT_FOR_MORE_EVIDENCE"
        best=None
    elif brain.get("action") in {"WAIT_FOR_VALID_OPPORTUNITY","RESEARCH_OR_WAIT"} and best["action"]=="PUBLISH_NOW":
        action="RESPECT_BRAIN_WAIT_STATE"
        best=None
    else: action="EXECUTE_BEST_SUPPORTED_ACTION"

    stamp=now()
    board={"schema_version":"16.0","generated_at":stamp,"status":"DECISION_READY" if best else "WAITING",
           "action":action,"selected_decision":best,"ranked_counterfactuals":candidates[:12],
           "model_notes":["Expected values are scenario estimates.","No causal certainty is claimed.","Verified revenue is never inferred from reach or engagement."],
           "verified_revenue":verified_revenue}
    history.append({"at":stamp,"action":action,"decision_id":best.get("decision_id") if best else None,"expected_value":best.get("expected_value") if best else None})
    write(BOARD,board); write(STATE,{"schema_version":"16.0","updated_at":stamp,"history":history[-100:]})
    write(INTEL/"creator_16_0_report.json",{"module":"creator_16_0_counterfactual_engine","generated_at":stamp,"status":board["status"],"action":action,"alternatives_evaluated":len(candidates),"selected_decision_id":best.get("decision_id") if best else None})
    print(json.dumps({"status":board["status"],"action":action,"alternatives_evaluated":len(candidates),"selected":best and best["action"]},indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
