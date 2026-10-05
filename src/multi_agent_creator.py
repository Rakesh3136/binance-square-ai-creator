"""NIC production creator entrypoint.

Content generation is now native to NIC. This module intentionally has no Gemini
or other hosted text-generation dependency.
"""
from __future__ import annotations
import json,os,re
from datetime import datetime,timezone
from pathlib import Path
from nic_native_writer import build

ROOT=Path(__file__).resolve().parents[1]
OUTPUT_DIR=ROOT/"data/reports"
OUTPUT_DIR.mkdir(parents=True,exist_ok=True)

def load(name):
    p=ROOT/name
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:return {}

def decision_contract(preflight,publication,result):
    sel=preflight.get("selected_opportunity") or {}
    research=result.get("research") or {}
    draft=result.get("draft") or {}
    visual=result.get("visual_plan") or {}
    return {
      "schema_version":"nic-decision-contract-2.0",
      "created_at":datetime.now(timezone.utc).isoformat(),
      "authority":"AUTHORITATIVE_DOWNSTREAM_GATES",
      "evidence":{"selected_symbol":publication.get("symbol") or sel.get("symbol"),"selected_lane":sel.get("category")},
      "thesis":{"summary":research.get("summary"),"strongest_signal":research.get("strongest_signal"),"opportunity_score":research.get("opportunity_score"),"counterpoint":(result.get("critique") or {}).get("summary")},
      "editorial":{"category":draft.get("content_category"),"generation_mode":"NIC_NATIVE","writer":"nic_native_writer"},
      "visual":{"type":visual.get("type","none"),"use_visual":bool(visual.get("use_visual")),"purpose":visual.get("purpose")},
      "quality":{"draft_quality_score":draft.get("quality_score"),"private_reasoning_exposed":False,"publication_status":"DRAFT_ONLY_NOT_PUBLISHED"},
      "hard_invariants":["verified_evidence_only","no_private_chain_of_thought_publication","no_unsupported_claims","no_duplicate_thesis","no_gate_bypass","no_external_text_model_dependency"]
    }

def main():
    preflight=load("data/live/editorial_preflight.json")
    publication=load("data/live/publication_context.json")
    context={"market":load("data/live/market_snapshot.json"),"news":load("data/live/news_snapshot.json"),"preflight":preflight,"publication":publication,"memory":load("analytics/strategy_memory.json"),"wte_strategy":load("data/live/wte_high_level_intelligence.json"),"wte_7day":load("data/live/write_to_earn_7day_status.json")}
    selected=preflight.get("selected_opportunity") or {}
    instruction=os.getenv("TOPIC","").strip() or selected.get("instruction") or "Build the strongest evidence-based story for the frozen opportunity."
    context["instruction"]=instruction
    result=build(context)
    research=result.get("research") or {}
    research["deep_research_provider"]="NIC_NATIVE"
    research["deep_research_status"]="native"
    result["research"]=research
    result["nic_decision_contract"]=decision_contract(preflight,publication,result)
    result["generated_at"]=datetime.now(timezone.utc).isoformat()
    result["status"]="DRAFT_ONLY_NOT_PUBLISHED"
    result["generation_mode"]="NIC_NATIVE"
    result["provider"]="NIC"
    result["model"]="nic-native-writer"
    symbol=str((result.get("draft") or {}).get("symbol") or selected.get("symbol") or "market-opportunity").lower()
    slug=re.sub(r"[^a-z0-9]+","-",symbol).strip("-") or "market-opportunity"
    out=OUTPUT_DIR/f"{slug}-multi-agent.json"
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"DRAFT_ONLY_NOT_PUBLISHED","report":str(out.relative_to(ROOT)),"quality_score":(result.get("draft") or {}).get("quality_score",0),"generation_mode":"NIC_NATIVE","provider":"NIC","external_text_model":False,"writer":"nic_native_writer"},indent=2))

if __name__=="__main__":
    main()
