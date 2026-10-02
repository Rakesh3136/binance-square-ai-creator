"""NIC 20.2 structural capability benchmark."""
from __future__ import annotations
import ast,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
MAP={"question_understanding":"nic_question_understanding.py","research":"nic_research_orchestrator.py","evidence_evaluation":"nic_evidence_registry.py","content_craft":"safe_creator_runner.py","market_analysis":"technical_enricher.py","visual_composition":"visual_renderer.py","publication_validation":"validate_visual.py","experimentation":"content_portfolio_planner.py"}
def main():
 role=json.loads((LIVE/"nic_role_contract.json").read_text()) if (LIVE/"nic_role_contract.json").exists() else {}; results=[]
 for cap in role.get("capabilities",[]):
  p=ROOT/"src"/MAP.get(cap,"__missing__.py"); ok=p.exists(); valid=False
  if ok:
   try: ast.parse(p.read_text()); valid=True
   except SyntaxError: pass
  results.append({"capability":cap,"module":p.name,"module_exists":ok,"syntax_valid":valid,"status":"BENCHMARK_VERIFIED" if ok and valid else "GAP"})
 out={"version":"20.2","status":"READY","results":results,"verified_capabilities":[r["capability"] for r in results if r["status"]=="BENCHMARK_VERIFIED"],"gaps":[r["capability"] for r in results if r["status"]=="GAP"],"policy":"Structural verification is not proof of production quality."}
 LIVE.mkdir(exist_ok=True); INTEL.mkdir(exist_ok=True); (LIVE/"nic_capability_benchmark.json").write_text(json.dumps(out,indent=2)+"\n"); (INTEL/"nic_capability_benchmark_report.json").write_text(json.dumps({"version":"20.2","status":"READY","verified":len(out["verified_capabilities"]),"gaps":len(out["gaps"])},indent=2)+"\n"); print(json.dumps({"status":"READY","verified":len(out["verified_capabilities"]),"gaps":len(out["gaps"])}))
if __name__=="__main__": main()
