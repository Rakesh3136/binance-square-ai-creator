"""Content Master Research & Training Layer 1.0.

Builds a bounded, evidence-first training curriculum from the creator's existing
research, audience outcomes, thesis memory, experiments and failure signals.
It does not fine-tune a model or invent facts. It produces structured lessons,
counterexamples, evaluation tasks and next-cycle editorial guidance.
"""
from __future__ import annotations
import hashlib, json, statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
INTEL = ROOT / "data/intelligence"
ANALYTICS = ROOT / "analytics"
OUT = LIVE / "content_master_training.json"
REPORT = INTEL / "content_master_training_report.json"
MEMORY = ANALYTICS / "content_master_memory.json"

SOURCES = {
    "research": LIVE / "research_intelligence.json",
    "active_research": LIVE / "creator_17_0_research_state.json",
    "audience": LIVE / "creator_22_2_editorial_intelligence.json",
    "draft_brief": LIVE / "creator_22_3_draft_brief.json",
    "brain": LIVE / "creator_9_0_brain_state.json",
    "control": LIVE / "creator_control_plane.json",
    "theses": INTEL / "thesis_ledger.json",
    "experiments": ANALYTICS / "creator_7_4_experiment_plan.json",
    "outcomes": LIVE / "creator_7_2_outcomes.jsonl",
    "improvement": ANALYTICS / "creator_11_0_improvement_state.json",
}

def load(path, default=None):
    try:
        if path.suffix == ".jsonl":
            rows=[]
            for line in path.read_text(encoding="utf-8").splitlines()[-1000:]:
                try:
                    x=json.loads(line)
                    if isinstance(x,dict): rows.append(x)
                except Exception: pass
            return rows
        x=json.loads(path.read_text(encoding="utf-8"))
        return x
    except Exception:
        return default if default is not None else {}

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()[:16]

def lesson(code, title, principle, evidence, drill, failure_mode):
    return {
        "lesson_id": code,
        "title": title,
        "principle": principle,
        "evidence": evidence,
        "training_drill": drill,
        "failure_mode": failure_mode,
        "epistemic_rule": "Never promote an observation to a fact without verification.",
    }

def main():
    s={k:load(p, [] if p.suffix==".jsonl" else {}) for k,p in SOURCES.items()}
    research=s["research"] if isinstance(s["research"],dict) else {}
    active=s["active_research"] if isinstance(s["active_research"],dict) else {}
    audience=s["audience"] if isinstance(s["audience"],dict) else {}
    improvement=s["improvement"] if isinstance(s["improvement"],dict) else {}
    outcomes=s["outcomes"] if isinstance(s["outcomes"],list) else []
    theses=s["theses"] if isinstance(s["theses"],dict) else {}

    lessons=[
      lesson("EVIDENCE_001","Evidence hierarchy",
        "Primary/verified evidence outranks discovery leads and narrative repetition.",
        {"official_evidence_count":active.get("evidence_summary",{}).get("official_feed",0),"discovery_leads":active.get("evidence_summary",{}).get("discovery_leads",0)},
        "Classify 20 claims as VERIFIED_FACT, DERIVED_OBSERVATION, INTERPRETATION, HYPOTHESIS or UNKNOWN.",
        "Turning a headline or social narrative into a factual claim."),
      lesson("NOVELTY_002","Novelty before publication",
        "A strong opportunity can still be blocked when the draft repeats recently published language or thesis.",
        {"research_queue":research.get("research_queue",[]),"active_contradictions":len(active.get("contradictions",[]) or [])},
        "Generate three materially different angles for the same evidence and reject semantic duplicates.",
        "Repeated sentence, repeated hook, repeated thesis."),
      lesson("MECHANISM_003","Mechanism over hype",
        "Every market claim should explain the observable mechanism and its invalidation conditions.",
        {"candidate_count":len(research.get("candidates",[]) or []),"thesis_count":len(theses)},
        "For each thesis write catalyst -> mechanism -> evidence -> invalidation.",
        "Price-only prediction with no causal/mechanistic explanation."),
      lesson("COUNTER_004","Adversarial thinking",
        "A publishable thesis must survive credible counter-evidence.",
        {"research_status":active.get("status"),"contradictions":active.get("contradictions",[])},
        "Produce bull/base/bear cases and identify the single strongest disconfirming fact.",
        "One-sided confirmation bias."),
      lesson("AUDIENCE_005","Learn without copying",
        "Historical engagement is observational guidance, not proof of causality or permission to copy creators.",
        {"sample_count":audience.get("source_samples",0),"dimensions":len(audience.get("guidance",[]) or [])},
        "Compare formats with at least three samples and label confidence as observational.",
        "Mistaking correlation for algorithm knowledge."),
      lesson("OUTCOME_006","Close the prediction loop",
        "Every eligible prediction/setup should later be reconciled with its realized outcome.",
        {"outcome_records":len(outcomes)},
        "For each historical setup, record thesis, timestamp, evidence, outcome and what changed.",
        "Learning only from publication-time information."),
    ]

    metrics=[]
    for r in outcomes[-100:]:
        if not isinstance(r,dict): continue
        vals=[r.get(k) for k in ("views","likes","replies","shares","followers_gained")]
        nums=[]
        for v in vals:
            try: nums.append(float(v))
            except Exception: pass
        if nums: metrics.append(sum(nums))
    performance_signal = round(statistics.mean(metrics),2) if metrics else None

    curriculum={
      "phase_1":"Evidence literacy",
      "phase_2":"Research and thesis construction",
      "phase_3":"Counterfactual/adversarial review",
      "phase_4":"Editorial originality",
      "phase_5":"Audience experimentation",
      "phase_6":"Outcome reconciliation",
      "phase_7":"Calibration and self-correction",
    }
    evaluation={
      "hard_failures":["fabricated source","unsupported factual claim","duplicate thesis","fake outcome","quality-gate bypass"],
      "tests":["evidence classification","source verification","mechanism extraction","counter-case generation","novelty rewrite","outcome post-mortem"],
      "minimum_evidence_before_signal":"verified multi-factor evidence contract",
      "scoring_policy":"Use component scores for diagnostics only; never convert them into permission to bypass mandatory gates.",
    }
    training={
      "schema_version":"content-master-1.0",
      "generated_at":datetime.now(timezone.utc).isoformat(),
      "training_id":digest({"lessons":lessons,"curriculum":curriculum}),
      "status":"READY",
      "mission":"Continuously improve research depth, factual discipline, originality, mechanism clarity, audience understanding and outcome calibration.",
      "lessons":lessons,
      "curriculum":curriculum,
      "evaluation_contract":evaluation,
      "source_health":{k: bool(v) for k,v in s.items()},
      "observational_performance_signal":performance_signal,
      "next_improvement":improvement.get("last_plan") or improvement.get("objective") or "RUN_NEXT_ADAPTIVE_EXPERIMENT",
      "hard_boundary":"This layer trains process and evaluation memory; it does not claim to train or fine-tune an external foundation model.",
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); ANALYTICS.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(training,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    history=load(MEMORY,{"history":[]})
    if not isinstance(history,dict): history={"history":[]}
    history.setdefault("history",[]).append({"training_id":training["training_id"],"generated_at":training["generated_at"],"lesson_count":len(lessons),"status":training["status"]})
    history["history"]=history["history"][-100:]
    history["latest"]=training
    MEMORY.write_text(json.dumps(history,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"module":"content_master_training","generated_at":training["generated_at"],"status":"READY","training_id":training["training_id"],"lesson_count":len(lessons),"source_health":training["source_health"]},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","training_id":training["training_id"],"lesson_count":len(lessons),"outcomes_used":len(outcomes)},indent=2))

if __name__=="__main__":
    main()
