"""NIC Experiment Governor — keyless evidence-based experiment capacity controller.

Controls experimentation without controlling truth or publication eligibility.
It consumes the existing adaptive experiment plan, Opportunity Genome and
verified monetization observations. It can continue, stop, replicate, or explore
but never forces a weak story, predicts revenue, or overrides safety/evidence
gates.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/"analytics/creator_7_4_experiment_plan.json"
GENOME=ROOT/"data/live/nic_opportunity_genome.json"
LAB=ROOT/"data/live/nic_revenue_pattern_lab.json"
PERF=ROOT/"analytics/creator_7_2_outcomes.jsonl"
OUT=ROOT/"data/live/nic_experiment_governor.json"
REPORT=ROOT/"data/intelligence/nic_experiment_governor_report.json"

def load(p, default):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
        return x if isinstance(x,type(default)) else default
    except Exception:
        return default

def rows(p):
    out=[]
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): out.append(x)
        except Exception: pass
    return out

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else 0.0
    except Exception: return 0.0

def outcome(x):
    if x.get("outcome_score") is not None: return num(x["outcome_score"])
    m=x.get("metrics") or {}
    views=num(m.get("views"))
    if views<=0: return 0.0
    return (num(m.get("likes"))+2*num(m.get("comments"))+3*num(m.get("shares"))+2*num(m.get("quotes")))/views*1000

def experiment_id(x):
    return str(x.get("experiment_id") or x.get("creator_7_4_experiment_id") or
               (x.get("experiment") or {}).get("experiment_id") or
               (x.get("learning") or {}).get("experiment_id") or "").strip()

def explicit_rows(data, eid):
    return [x for x in data if experiment_id(x)==eid] if eid else []

def governor_decision(plan, data, genome, lab):
    current=plan.get("current_experiment") if isinstance(plan,dict) else None
    history=plan.get("completed_experiments",[]) if isinstance(plan,dict) else []
    if not isinstance(history,list): history=[]
    if not isinstance(current,dict) or current.get("status")!="ACTIVE":
        return {
            "decision":"START_EXPERIMENT",
            "reason":"No active experiment exists; use the existing 7.4 planner.",
            "capacity_share":0.15,
            "experiment":None,
            "stop_reason":None,
            "replication_ready":False,
        }

    eid=str(current.get("experiment_id") or "")
    treated=explicit_rows(data,eid)
    n=len(treated)
    target=max(1,int(current.get("sample_target") or 10))
    result=(plan.get("last_evaluation") or {}) if isinstance(plan,dict) else {}
    # Never stop merely because a proxy metric is weak before enough explicit data.
    if n < 3:
        return {
            "decision":"CONTINUE_ACTIVE",
            "reason":"Insufficient explicit experiment attribution; keep the test eligible but do not force publication.",
            "capacity_share":0.15,
            "experiment":current,
            "stop_reason":None,
            "replication_ready":False,
        }

    scores=[outcome(x) for x in treated]
    avg=sum(scores)/len(scores) if scores else 0.0
    control=num(result.get("control_median"))
    lift=num(result.get("lift_percent"))

    # Hard stop only for a sufficiently sampled, explicitly attributed test with
    # a materially negative observed result. This is a resource decision, not a
    # claim that the variable caused the result.
    if n>=6 and control>0 and lift <= -30:
        return {
            "decision":"STOP_UNDERPERFORMING",
            "reason":"Explicitly attributed observations are materially below the recorded control baseline; stop allocating experiment capacity and explore another variable.",
            "capacity_share":0.0,
            "experiment":current,
            "stop_reason":"observed_negative_lift",
            "replication_ready":False,
            "observed_sample":n,
            "target":target,
            "treatment_mean":round(avg,4),
            "control_median":round(control,4),
            "lift_percent":round(lift,2),
        }

    # Replication is allowed only after a completed test with explicit attribution
    # and a non-negative observed result. It remains subordinate to natural story fit.
    if n>=6 and control>0 and lift >= 15:
        return {
            "decision":"COMPLETE_AND_REPLICATE",
            "reason":"The active test has enough explicit observations and a positive observed comparison; use a fresh eligible story for bounded replication.",
            "capacity_share":0.25,
            "experiment":current,
            "stop_reason":None,
            "replication_ready":True,
            "observed_sample":n,
            "target":target,
            "treatment_mean":round(avg,4),
            "control_median":round(control,4),
            "lift_percent":round(lift,2),
        }

    # Protect exploration when a test reaches its sample target without clear evidence.
    if n>=target:
        return {
            "decision":"CLOSE_INCONCLUSIVE_EXPLORE",
            "reason":"The experiment reached its target without a sufficiently clear observed signal; close it and allocate capacity to a different test.",
            "capacity_share":0.10,
            "experiment":current,
            "stop_reason":"inconclusive_at_target",
            "replication_ready":False,
            "observed_sample":n,
            "target":target,
            "treatment_mean":round(avg,4),
            "control_median":round(control,4),
            "lift_percent":round(lift,2),
        }

    return {
        "decision":"CONTINUE_ACTIVE",
        "reason":"Keep the current test stable while explicit observations accumulate; never publish filler to hit the sample target.",
        "capacity_share":0.15,
        "experiment":current,
        "stop_reason":None,
        "replication_ready":False,
        "observed_sample":n,
        "target":target,
        "treatment_mean":round(avg,4),
        "control_median":round(control,4),
        "lift_percent":round(lift,2),
    }

def main():
    plan=load(PLAN,{})
    genome=load(GENOME,{})
    lab=load(LAB,{})
    data=rows(PERF)
    decision=governor_decision(plan,data,genome,lab)
    repeatable=len(genome.get("repeatable_patterns",[])) if isinstance(genome,dict) else 0
    verified=len(genome.get("verified_patterns",[])) if isinstance(genome,dict) else 0
    state={
        "version":"1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY",
        "decision":decision,
        "capacity_policy":{
            "experiment_capacity_is_a_soft_budget":True,
            "maximum_experiment_share":0.25,
            "zero_capacity_when_stopped":True,
            "replication_requires_fresh_eligible_story":True,
            "exploration_preserved":True,
            "no_forced_story":True,
        },
        "evidence_summary":{
            "genome_repeatable_patterns":repeatable,
            "genome_verified_patterns":verified,
            "revenue_lab_status":lab.get("status"),
        },
        "handoff":{
            "publication_eligibility":"unchanged_and_authoritative",
            "signal_first":"unchanged_and_authoritative",
            "safety_and_integrity":"unchanged_and_authoritative",
            "revenue":"verified_only",
        },
        "rules":[
            "Governor allocates experiment capacity; it does not decide whether a story is publishable.",
            "Do not infer causality from observational lift.",
            "Do not infer revenue from views, engagement, prediction success or clicks.",
            "Never manufacture a story to complete an experiment.",
            "Stop/replicate decisions are resource decisions, not claims of market or audience causality.",
            "A replication must use a fresh eligible opportunity and retain the experiment lineage.",
            "Missing evidence remains missing.",
        ],
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":"READY","decision":decision.get("decision"),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","decision":decision.get("decision"),"capacity_share":decision.get("capacity_share"),"experiment_id":(decision.get("experiment") or {}).get("experiment_id") if isinstance(decision.get("experiment"),dict) else None},ensure_ascii=False))

if __name__=="__main__":
    main()
