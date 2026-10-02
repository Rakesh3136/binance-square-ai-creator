"""NIC 20 — Role contract compiler.
Turns a natural-language role into an explicit, auditable operating contract.
No hidden chain-of-thought; stores only structured objectives, constraints and capabilities.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/live/nic_role_contract.json"
ROLE=ROOT/"data/live/nic_role_request.json"
DEFAULT={
    "role":"binance_square_creator",
    "mission":"Create original, useful, evidence-grounded Binance Square content and continuously improve from verified outcomes.",
    "responsibilities":["understand audience and task","research evidence","analyze","write","design visuals","validate","publish","measure","learn","improve"],
    "capabilities":["question_understanding","research","evidence_evaluation","market_analysis","content_craft","visual_composition","publication_validation","outcome_attribution","experimentation"],
    "constraints":["do not fabricate facts","do not infer revenue without explicit verification","respect platform and publication gates","preserve unknowns as unknown","do not copy creators"],
    "evaluation":["evidence quality","reader usefulness","originality","clarity","visual quality","publication integrity","verified outcomes","learning value"]
}
def main():
    try: req=json.loads(ROLE.read_text(encoding="utf-8")) if ROLE.exists() else {}
    except Exception: req={}
    c=dict(DEFAULT)
    if isinstance(req,dict):
        if req.get("role"): c["role"]=str(req["role"])
        if req.get("mission"): c["mission"]=str(req["mission"])
        for k in ("responsibilities","capabilities","constraints","evaluation"):
            if isinstance(req.get(k),list) and req[k]: c[k]=[str(x) for x in req[k]]
    c["version"]="20.0"; c["generated_at"]=datetime.now(timezone.utc).isoformat(); c["status"]="READY"; c["learning_policy"]="research -> execute -> verify -> learn -> update"
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(c,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","role":c["role"],"capability_count":len(c["capabilities"])},ensure_ascii=False))
if __name__=="__main__": main()
