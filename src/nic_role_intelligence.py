"""NIC 20 — Role Intelligence coordinator.
Creates a durable role/task/capability snapshot from existing NIC evidence.
It does not expose private chain-of-thought and does not claim unsupported learning.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"; OUT=LIVE/"nic_role_intelligence.json"; REPORT=INTEL/"nic_role_intelligence_report.json"
def load(p,d):
 try:
  x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
  return x if isinstance(x,dict) else d
 except Exception:return d
def main():
 role=load(LIVE/"nic_role_contract.json",{}); task=load(LIVE/"nic_task_plan.json",{}); gap=load(LIVE/"nic_capability_gap.json",{}); memory=load(LIVE/"nic_memory_graph.json",{})
 snapshot={"version":"20.0","status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),"role":role,"task":task,"capability_gap":gap,"memory_summary":{"nodes":memory.get("node_count",0),"edges":memory.get("edge_count",0)},"operating_loop":["understand","research","plan","execute","verify","measure","learn","improve"],"evidence_policy":["verified facts outrank inference","unknown stays unknown","external creator patterns are studied, not copied","revenue requires explicit verification"]}
 LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");REPORT.write_text(json.dumps({"version":"20.0","status":"READY","role":role.get("role"),"task_id":task.get("task_id"),"capability_gaps":len(gap.get("capability_gaps",[]))},indent=2)+"\n",encoding="utf-8");print(json.dumps({"status":"READY","role":role.get("role"),"task_id":task.get("task_id")},ensure_ascii=False))
if __name__=="__main__":main()
