"""NIC 20.1 — Question Understanding / Task Compiler front-end.
Converts a natural-language task request into a deterministic task brief.
No hidden reasoning is persisted; only structured decisions, constraints and unknowns.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQ=ROOT/"data/live/nic_task_request.json"
ROLE=ROOT/"data/live/nic_role_contract.json"
OUT=ROOT/"data/live/nic_question_understanding.json"

def load(p, default):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
        return x if isinstance(x, type(default)) else default
    except Exception:
        return default

def classify(task: str):
    t=task.lower()
    intents=[]
    for key,terms in {
        "create_content":["create","write","post","content","article"],
        "research":["research","investigate","study","find out","sources","google"],
        "analyze":["analyze","analysis","compare","why","impact","risk"],
        "solve_problem":["solve","fix","problem","error","issue","how do i"],
        "improve_role":["improve","upgrade","learn","better","capability"],
    }.items():
        if any(x in t for x in terms): intents.append(key)
    return intents or ["general_task"]

def main():
    req=load(REQ,{})
    role=load(ROLE,{})
    task=str(req.get("task") or "Create the next best publishable Binance Square content opportunity using current verified evidence.").strip()
    constraints=list(req.get("constraints") or [])
    intent=classify(task)
    unknowns=[]
    if not req.get("task"): unknowns.append("The task was not explicitly supplied; a default creator task was used.")
    if "research" in intent or "create_content" in intent:
        unknowns.append("Fresh external evidence must be retrieved before factual claims are treated as current.")
    key=hashlib.sha256((role.get("role","")+task).encode()).hexdigest()[:16]
    out={
      "version":"20.1","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),
      "request_id":"nic-question-"+key,"role":role.get("role"),"task":task,
      "intent_classes":intent,"constraints":constraints,
      "deliverable":"structured_answer_or_publishable_content",
      "required_operations":["understand","retrieve_evidence","evaluate_sources","solve_or_create","verify","record_learning"],
      "evidence_policy":["primary_or_official_when_available","fresh_sources_for_time_sensitive_claims","separate observation_from_inference","preserve_unknowns"],
      "unknowns":unknowns
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","intents":intent,"request_id":out["request_id"]},ensure_ascii=False))
if __name__=="__main__": main()
