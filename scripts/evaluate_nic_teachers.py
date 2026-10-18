"""Run a small, paid, side-by-side NIC teacher-model evaluation.

This deliberately requires --live. It writes outputs for human scoring; it does not
train/distill a model or declare a winner automatically.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nic_chat_server import ChatError, generate_reply

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="explicitly allow paid provider calls")
    parser.add_argument("--tasks", default=str(ROOT / "data/benchmarks/nic_teacher_tasks.json"))
    parser.add_argument("--output", default=str(ROOT / "data/reports/nic_teacher_eval.json"))
    parser.add_argument("--providers", default="anthropic,muse", help="comma-separated provider names")
    args = parser.parse_args()
    if not args.live:
        parser.error("Refusing provider calls without explicit --live (these calls may incur cost).")
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or not tasks or len(tasks) > 50:
        parser.error("Benchmark must contain between 1 and 50 tasks.")
    results = []
    for provider in [p.strip().lower() for p in args.providers.split(",") if p.strip()]:
        for task in tasks:
            env = dict(os.environ)
            env["NIC_CHAT_PROVIDER"] = provider
            try:
                result = generate_reply([{"role":"user","content":task["prompt"]}], environ=env)
                results.append({"task_id":task["id"],"provider_requested":provider,
                    "provider_returned":result["provider"],"model":result["model"],
                    "reply":result["reply"],"rubric":task.get("rubric",[]),"status":"COMPLETED"})
            except ChatError as exc:
                results.append({"task_id":task["id"],"provider_requested":provider,
                    "status":"FAILED","error":str(exc),"rubric":task.get("rubric",[])})
    payload = {"schema_version":"nic-teacher-eval-1","created_at":datetime.now(timezone.utc).isoformat(),
        "evaluation_type":"human_scored_comparison_not_distillation",
        "task_count":len(tasks),"results":results,
        "scoring_note":"Score each response blind for factual accuracy, evidence handling, originality, risk discipline, usefulness, latency and cost. Do not infer training permission from API access."}
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(output),"task_count":len(tasks),"attempts":len(results),
        "completed":sum(r["status"]=="COMPLETED" for r in results),
        "failed":sum(r["status"]=="FAILED" for r in results)},indent=2))
    return 0 if all(r["status"]=="COMPLETED" for r in results) else 2

if __name__ == "__main__":
    raise SystemExit(main())
