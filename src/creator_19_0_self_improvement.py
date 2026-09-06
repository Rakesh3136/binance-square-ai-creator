"""Creator 19.0 — Self-Improvement Engine.

Finds recurring weaknesses in the creator system, scores improvement targets,
and records safe, testable adjustments for future cycles. It never edits
credentials, bypasses gates, fabricates outcomes, or claims that a change
worked without measured evidence.
"""
from __future__ import annotations
import hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
ANALYTICS=ROOT/"analytics"; LIVE=ROOT/"data"/"live"; INTEL=ROOT/"data"/"intelligence"
STATE=ANALYTICS/"creator_19_0_improvement_memory.json"
BOARD=LIVE/"creator_19_0_improvement_board.json"


def load(path:Path, default:Any)->Any:
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError,OSError):return default

def save(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def num(x:Any,d=0.0)->float:
    try:
        v=float(x)
        return v if math.isfinite(v) else d
    except (TypeError,ValueError):return d

def now()->str:return datetime.now(timezone.utc).isoformat()
def iid(x:Any)->str:return "imp19_"+hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:14]

def main()->int:
    strategy=load(ANALYTICS/"strategy_memory.json",{})
    outcome=load(ANALYTICS/"creator_7_2_state.json",{})
    causal=load(ANALYTICS/"creator_7_3_causal_effects.json",{})
    experiment=load(LIVE/"creator_12_0_active_experiment.json",{})
    research=load(LIVE/"creator_17_0_research_state.json",{})
    decision=load(LIVE/"creator_16_0_decision_board.json",{})
    reliability=load(ANALYTICS/"creator_10_0_reliability_state.json",{})
    repair=load(ANALYTICS/"creator_10_1_repair_state.json",{})
    memory=load(STATE,{"history":[],"tested_changes":{}})

    targets=[]
    def add(area,signal,severity,action,reason):
        targets.append({"area":area,"signal":signal,"severity":round(max(0,min(1,severity)),3),"recommended_change":action,"reason":reason})

    if isinstance(reliability,dict) and str(reliability.get("status","")).upper() in {"DEGRADED","FAILURE","RETRYING"}:
        add("reliability","recent reliability degradation",0.95,"stabilize failing stage before optimization","Reliability dominates growth optimization when the publishing pipeline is unstable.")
    if isinstance(repair,dict) and str(repair.get("status","")).upper() in {"REVIEW_REQUIRED","BLOCKED"}:
        add("root_cause","recurring or blocked repair state",0.92,"diagnose root cause and create a bounded test","Repeated failures should be diagnosed rather than patched blindly.")

    if isinstance(research,dict):
        impact=str(research.get("decision_impact", ""))
        if impact=="BLOCK_UNTIL_VERIFIED":
            add("evidence","research requires verification",0.88,"increase verification priority and avoid unsupported execution","The evidence layer explicitly says material decisions must wait for verification.")
        elif impact in {"RE_EVALUATE_COUNTERFACTUALS","RE_RANK_OPPORTUNITIES"}:
            add("decision_quality","new evidence can change ranking",0.72,"re-score opportunities/counterfactuals before next major action","Active research reports a possible decision-impacting update.")

    if isinstance(experiment,dict) and experiment:
        samples=num(experiment.get("samples",experiment.get("sample_count")),0)
        target=num(experiment.get("sample_target"),10)
        if target and samples < target:
            add("experimentation","active experiment under-sampled",0.65,"continue current experiment before starting another","Preserves clean measurement of the primary variable.")

    if isinstance(causal,dict):
        effects=causal.get("effects",causal.get("recommendations",[]))
        if isinstance(effects,list) and len(effects)==0:
            add("learning","no robust repeated effects yet",0.48,"keep exploration active and gather more outcomes","Absence of evidence is not evidence of a winner.")

    verified_revenue=0.0
    monet=load(ANALYTICS/"creator_8_0_monetization_engine.json",{})
    for k in ("verified_revenue","revenue_verified","verified_earnings","earnings_verified"):
        if isinstance(monet,dict) and isinstance(monet.get(k),(int,float)):
            verified_revenue=max(verified_revenue,num(monet[k]))
    if verified_revenue<=0:
        add("monetization","no verified revenue observed","0.55","optimize verified conversion signals without assuming revenue","Reach and engagement are not revenue; revenue claims require explicit verification.")

    if not targets:
        add("global","no critical weakness detected",0.20,"run measurement-first monitoring","The system currently has no evidence-backed high-severity weakness.")

    targets.sort(key=lambda x:(x["severity"],x["area"]),reverse=True)
    top=targets[:8]
    changes=[]
    tested=memory.get("tested_changes",{}) if isinstance(memory,dict) else {}
    for t in top[:4]:
        change_id=iid(t)
        prior=tested.get(change_id,{}) if isinstance(tested,dict) else {}
        changes.append({
            "improvement_id":change_id,
            "area":t["area"],
            "change":t["recommended_change"],
            "status":"PROPOSED" if not prior else prior.get("status","PROPOSED"),
            "measurement":"compare the next eligible cycles against the pre-change baseline",
            "success_rule":"repeat only after measured improvement across sufficient observations",
            "rollback_rule":"do not reuse if measured performance worsens or a quality/reliability gate degrades",
        })

    action="RUN_SAFE_MEASUREMENT_CYCLE"
    if any(x["severity"]>=0.85 for x in top): action="FIX_HIGHEST_SEVERITY_SYSTEM_RISK"
    elif any(x["area"] in {"evidence","decision_quality"} for x in top): action="RE_EVALUATE_DECISIONS_WITH_NEW_EVIDENCE"

    stamp=now()
    board={"schema_version":"19.0","generated_at":stamp,"status":"IMPROVEMENT_PLAN_READY","action":action,"priority_targets":top,"proposed_changes":changes,"verified_revenue":verified_revenue,"hard_constraints":["no blind self-modification","no credential/security changes","no quality-gate bypass","no fabricated outcomes","no inferred revenue","no fake engagement","no guaranteed returns"]}
    save(BOARD,board)
    history=memory.get("history",[]) if isinstance(memory,dict) else []
    history.append({"at":stamp,"action":action,"top_area":top[0]["area"] if top else None,"top_severity":top[0]["severity"] if top else 0})
    tested=dict(tested) if isinstance(tested,dict) else {}
    for c in changes: tested[c["improvement_id"]]={"last_seen":stamp,"status":c["status"]}
    save(STATE,{"schema_version":"19.0","updated_at":stamp,"history":history[-100:],"tested_changes":tested})
    strategy.setdefault("creator_19_0",{})
    strategy["creator_19_0"]={"action":action,"top_area":top[0]["area"] if top else None,"top_severity":top[0]["severity"] if top else 0,"improvement_count":len(changes),"verified_revenue":verified_revenue}
    strategy.setdefault("learning_overlay",{})["self_improvement"]=strategy["creator_19_0"]
    save(ANALYTICS/"strategy_memory.json",strategy)
    save(INTEL/"creator_19_0_report.json",{"module":"creator_19_0_self_improvement","generated_at":stamp,"action":action,"target_count":len(top),"proposed_change_count":len(changes),"top_area":top[0]["area"] if top else None,"top_severity":top[0]["severity"] if top else 0})
    print(json.dumps({"status":"OK","action":action,"top_area":top[0]["area"] if top else None,"proposed_changes":len(changes)},indent=2))
    return 0

if __name__=="__main__":raise SystemExit(main())
