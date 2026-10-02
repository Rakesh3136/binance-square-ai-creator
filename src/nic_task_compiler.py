"""NIC 20 — Task compiler.
Compiles a role request into an executable, evidence-aware task plan.
"""
from __future__ import annotations
import json,hashlib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ROLE=ROOT/"data/live/nic_role_contract.json"; REQ=ROOT/"data/live/nic_task_request.json"; OUT=ROOT/"data/live/nic_task_plan.json"
def main():
    try:r=json.loads(REQ.read_text(encoding="utf-8")) if REQ.exists() else {}
    except Exception:r={}
    role=json.loads(ROLE.read_text(encoding="utf-8")) if ROLE.exists() else {}
    task=str(r.get("task") or "Create the next best publishable Binance Square content opportunity using current verified evidence.")
    steps=[
      {"id":"understand","action":"define_goal_and_constraints"},
      {"id":"research","action":"collect_and_classify_evidence"},
      {"id":"analyze","action":"compare_hypotheses_and_unknowns"},
      {"id":"craft","action":"produce_original_content_and_visual_plan"},
      {"id":"verify","action":"run_quality_and_integrity_checks"},
      {"id":"learn","action":"record outcome and reusable lesson"}]
    key=hashlib.sha256((role.get("role","")+task).encode()).hexdigest()[:16]
    out={"version":"20.0","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),"task_id":"nic20-"+key,"role":role.get("role"),"task":task,"steps":steps,"required_evidence":["primary_or_official_when_available","fresh_context_when_time_sensitive","explicit_unknowns"],"success_conditions":["publishable_or_actionable_output","evidence_traceability","no fabricated facts","lesson_recorded"]}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");print(json.dumps({"status":"READY","task_id":out["task_id"]},ensure_ascii=False))
if __name__=="__main__":main()
