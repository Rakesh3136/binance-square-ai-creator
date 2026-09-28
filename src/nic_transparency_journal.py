"""Build a public-safe NIC decision trace.

The trace exposes auditable decision information (evidence, alternatives,
uncertainty, counter-evidence, invalidation conditions and outcomes) without
exposing hidden chain-of-thought or private internal reasoning.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_transparency_journal.json"; REPORT=INTEL/"nic_transparency_report.json"

SOURCES={
 "prediction":LIVE/"nic_prediction_engine.json",
 "accuracy_gate":LIVE/"nic_prediction_accuracy_gate.json",
 "learning":LIVE/"learning_engine.json",
 "self_training":LIVE/"creator_self_training.json",
 "content_master":LIVE/"content_master_training.json",
 "opportunity_genome":LIVE/"nic_opportunity_genome.json",
 "experiment_governor":LIVE/"nic_experiment_governor.json",
 "publication":LIVE/"publisher_result.json",
 "publication_payload":LIVE/"publication_payload.json",
 "dashboard":LIVE/"nic_dashboard.json",
 "thesis_ledger":ROOT/"data/intelligence/thesis_ledger.json",
 "creator_brain":LIVE/"creator_brain_decision.json",
 "adversarial_brain":LIVE/"adversarial_brain.json",
 "decision_ensemble":LIVE/"decision_ensemble_gate.json",
}

def load(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}

def first(d,*keys):
    for key in keys:
        value=d.get(key)
        if value not in (None,"",[],{}):
            return value
    return None

def compact(value, limit=500):
    if value in (None,"",[],{}):
        return None
    text=json.dumps(value,ensure_ascii=False,default=str) if not isinstance(value,str) else value
    return text[:limit]

def main():
    now=datetime.now(timezone.utc).isoformat()
    data={k:load(v) for k,v in SOURCES.items()}

    # Keep this explicit rather than relying on dictionary iteration order.
    # It prevents a newly added telemetry source from silently breaking the
    # transparency journal with a tuple-unpack error.
    prediction=data["prediction"]
    accuracy=data["accuracy_gate"]
    learning=data["learning"]
    training=data["self_training"]
    master=data["content_master"]
    genome=data["opportunity_genome"]
    experiments=data["experiment_governor"]
    publication=data["publication"]
    payload=data["publication_payload"]
    theses=data["thesis_ledger"]
    brain=data["creator_brain"]
    adversarial=data["adversarial_brain"]
    ensemble=data["decision_ensemble"]

    symbol=first(prediction,"symbol","asset") or first(payload,"symbol")
    direction=first(prediction,"direction","bias")
    evidence=first(prediction,"evidence_score","score")
    confidence=first(prediction,"confidence","confidence_score")
    gate=first(accuracy,"status","decision","gate")
    experiment_id=first(experiments,"experiment_id") or first(payload,"experiment_id")

    lessons=[]
    for obj,label in ((learning,"learning engine"),(training,"self-training"),
                      (master,"content master"),(genome,"opportunity genome")):
        for key in ("lesson","latest_lesson","learning","insight","summary"):
            value=obj.get(key)
            if isinstance(value,str) and value.strip():
                lessons.append({"source":label,"text":value.strip()})
                break
        if len(lessons)>=4:
            break

    observed=[x for x in [
        f"Primary asset: {symbol}" if symbol else None,
        f"Modelled direction/bias: {direction}" if direction else None,
        f"Evidence score: {evidence}" if evidence is not None else None,
        f"Accuracy gate: {gate}" if gate else None
    ] if x]

    candidates=[]
    raw=theses.get("theses") if isinstance(theses,dict) else None
    if isinstance(raw,list):
        for i,t in enumerate(raw[:5]):
            if isinstance(t,dict):
                candidates.append({
                    "index":i,
                    "observation":compact(t.get("observation")),
                    "mechanism":compact(t.get("mechanism")),
                    "risk":compact(t.get("contradiction") or t.get("risk")),
                    "why_reader_cares":compact(t.get("why_reader_care") or t.get("reader_value"))
                })

    selected=first(brain,"selected_thesis","thesis","selected_opportunity")
    counter=first(adversarial,"counter_evidence","counterpoint","risk","failure_condition")
    invalidation=first(prediction,"invalidation","invalidation_condition","failure_condition")

    public_reasoning={
        "what_i_saw":observed,
        "alternatives_considered":candidates,
        "why_i_chose_it":"NIC selected the evidence-backed opportunity represented by the authoritative decision artifacts; this field records the decision basis, not hidden internal reasoning.",
        "counter_evidence":compact(counter),
        "uncertainty":compact(first(brain,"uncertainty","confidence_notes") or first(adversarial,"uncertainty")),
        "what_would_change_my_mind":compact(invalidation) or "A verified outcome that contradicts the current prediction, a failed evidence gate, or materially new market/news evidence.",
        "next_test":experiments.get("decision") or experiments.get("selected_strategy") or experiments.get("strategy") or experiment_id,
    }

    journal={
        "schema_version":"3.0",
        "timestamp":now,
        "run_id":os.getenv("GITHUB_RUN_ID",""),
        "run_number":os.getenv("GITHUB_RUN_NUMBER",""),
        "purpose":"Transparent NIC decision and learning trace",
        "transparency_policy":{
            "exposes":["decision_summary","evidence_summary","candidate_theses","counter_evidence","uncertainty","invalidation_conditions","verified_outcome","lessons","next_experiment"],
            "does_not_expose":["hidden_chain_of_thought","private_internal_reasoning"],
            "reason":"The trace is designed to be inspectable, reproducible and safe to publish without pretending to reveal private model reasoning."
        },
        "decision_summary":{
            "symbol":symbol,"direction":direction,"evidence_score":evidence,
            "confidence":confidence,"accuracy_gate":gate,
            "experiment_id":experiment_id,
            "ensemble_decision":first(ensemble,"decision","status")
        },
        "what_i_observed":observed,
        "candidate_theses":candidates,
        "decision_basis":{
            "selected_thesis":compact(selected),
            "counter_evidence":compact(counter),
            "invalidation":compact(invalidation)
        },
        "lessons":lessons,
        "outcome":{
            "publication_status":first(publication,"status"),
            "post_id":first(publication,"post_id","canonical_post_id"),
            "publication_proof":first(publication,"publication_proof")
        },
        "next_experiment":{"experiment_id":experiment_id,"governor":public_reasoning["next_test"]},
        "public_reflection":public_reasoning,
        "shareable_note":(
            "NIC field note — "
            +(f"I focused on {symbol}. " if symbol else "")
            +(f"The evidence score was {evidence}. " if evidence is not None else "")
            +(f"The modelled direction was {direction}. " if direction else "")
            +"I will compare the decision with the verified outcome and use that result to calibrate the next cycle."
        )
    }

    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(journal,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps(journal,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":"TRANSPARENCY_TRACE_READY",
        "symbol":symbol,
        "candidate_theses":len(candidates),
        "lessons":len(lessons),
        "public_reflection":public_reasoning
    },indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
