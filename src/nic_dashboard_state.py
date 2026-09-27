"""Build a read-only NIC cockpit snapshot from committed pipeline artifacts."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; OUT=LIVE/"nic_dashboard.json"
SOURCES={
 "nic_core":"nic_core_state.json","contract":"nic_decision_contract.json",
 "transparency":"nic_transparency_journal.json","mesh":"agent_mesh_300.json",
 "adversarial":"adversarial_brain_review.json","counterfactual":"creator_16_0_decision_board.json",
 "research":"creator_17_0_research_state.json","creator_brain":"creator_brain_decision.json",
 "ensemble":"decision_ensemble.json","jev":"jev_decision.json","production":"production_decision.json",
 "publication":"publication_result.json","outcomes":"prediction_outcomes.json","learning":"learning_report.json",
 "revenue":"creator_8_4_monetization_feedback.json","thesis_ledger":"thesis_ledger.json"
}
def load(name):
 try:
  v=json.loads((LIVE/name).read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
 except Exception:return {}
def first(d,*keys,default=None):
 for k in keys:
  v=d.get(k)
  if v not in (None,"",[],{}): return v
 return default
def status(d):
 if not d:return "UNAVAILABLE"
 v=first(d,"decision","action","status","state",default="AVAILABLE")
 if isinstance(v,bool): return "PASS" if v else "BLOCK"
 return str(v).upper()
def specialist(k,d):
 return {"module":k,"available":bool(d),"status":status(d),"confidence":first(d,"confidence","score","evidence_score","research_score"),"reason":first(d,"reason","rationale","summary","thesis","recommendation",default=None)}
def main():
 docs={k:load(v) for k,v in SOURCES.items()}
 nic=docs["nic_core"]; contract=docs["contract"]; trace=docs["transparency"]; thesis=docs["thesis_ledger"]
 agents=[specialist(k,docs[k]) for k in ("adversarial","counterfactual","research","creator_brain","ensemble","jev")]
 pub=docs["publication"]; prod=docs["production"]; outcomes=docs["outcomes"]; learning=docs["learning"]; revenue=docs["revenue"]
 state={
  "schema_version":"NIC-COCKPIT-2.0","generated_at":datetime.now(timezone.utc).isoformat(),"source":"committed_repository_artifacts","refresh_mode":"post_cycle_truth_snapshot",
  "current_decision":{"symbol":first(nic,"symbol","asset"),"direction":first(nic,"direction","bias"),"evidence_score":first(nic,"evidence_score","score"),"thesis_id":first(nic,"thesis_id"),"thesis":first(nic,"editorial_thesis","thesis"),"confidence":first(nic,"confidence","confidence_score")},
  "decision_contract":contract,
  "transparent_trace":trace,
  "thesis_memory":{"available":bool(thesis),"active_thesis":first(thesis,"active_thesis","current_thesis","thesis"),"status":status(thesis),"lessons":first(thesis,"lessons","learning","insights",default=[])},
  "specialists":agents,
  "decision_path":[{"stage":"signal","status":status(nic)},{"stage":"adversarial","status":status(docs["adversarial"])},{"stage":"counterfactual","status":status(docs["counterfactual"])},{"stage":"research","status":status(docs["research"])},{"stage":"ensemble","status":status(docs["ensemble"])},{"stage":"jev","status":status(docs["jev"])},{"stage":"production","status":status(prod)},{"stage":"publication","status":status(pub)}],
  "learning_loop":{"outcomes_available":bool(outcomes),"learning_available":bool(learning),"revenue_feedback_available":bool(revenue),"outcome":first(outcomes,"summary","status","result"),"lesson":first(learning,"summary","status","result"),"revenue_feedback":first(revenue,"summary","status","result"),"policy":"verified_observations_only"},
  "operator_view":{"what_nic_saw":first(trace,"what_i_observed",default=[]),"why_nic_chose_it":first(trace,"public_reflection",default={}),"what_could_change_the_decision":(trace.get("public_reflection") or {}).get("what_could_change_my_mind") if isinstance(trace.get("public_reflection"),dict) else None,"next_test":(trace.get("public_reflection") or {}).get("next_test") if isinstance(trace.get("public_reflection"),dict) else None},
  "integrity":{"read_only":True,"no_private_chain_of_thought":True,"no_simulated_status":True,"publication_authority":"deterministic downstream gates"}
 }
 LIVE.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print(json.dumps({"status":"NIC_COCKPIT_READY","schema_version":state["schema_version"],"symbol":state["current_decision"]["symbol"],"thesis_id":state["current_decision"]["thesis_id"],"specialists":len(agents)},indent=2))
if __name__=="__main__":main()
