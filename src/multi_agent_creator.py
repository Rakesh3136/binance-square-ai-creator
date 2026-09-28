from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
from nic_model_router import generate as nic_generate

ROOT=Path(__file__).resolve().parents[1]
OUTPUT_DIR=ROOT/"data/reports"; OUTPUT_DIR.mkdir(parents=True,exist_ok=True)

def load(name):
    p=ROOT/name
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

def normalize(v): return v if isinstance(v,dict) else ({"summary":v} if isinstance(v,str) else {})

def parse(text):
    text=re.sub(r"^```(?:json)?\s*|\s*```$","",str(text or "").strip())
    v=json.loads(text)
    if not isinstance(v,dict): raise ValueError("non-object response")
    return v

def decision_contract(preflight,publication,research,critique,draft,visual):
    selected=preflight.get("selected_opportunity") or {}
    return {"schema_version":"nic-decision-contract-1.1","created_at":datetime.now(timezone.utc).isoformat(),"authority":"AUTHORITATIVE_DOWNSTREAM_GATES","evidence":{"selected_symbol":publication.get("symbol") or selected.get("symbol"),"selected_lane":selected.get("category") or selected.get("reason")},"thesis":{"summary":research.get("summary"),"strongest_signal":research.get("strongest_signal"),"opportunity_score":research.get("opportunity_score"),"counterpoint":critique.get("summary")},"editorial":{"category":draft.get("content_category"),"experiment_id":draft.get("experiment_id"),"generation_mode":draft.get("generation_mode")},"visual":{"type":visual.get("type","none"),"use_visual":bool(visual.get("use_visual")),"provider":visual.get("provider"),"purpose":visual.get("purpose")},"quality":{"draft_quality_score":draft.get("quality_score"),"private_reasoning_exposed":False,"publication_status":"DRAFT_ONLY_NOT_PUBLISHED"},"hard_invariants":["verified_evidence_only","no_private_chain_of_thought_publication","no_unsupported_claims","no_duplicate_thesis","no_gate_bypass"]}

def main():
    preflight=load("data/live/editorial_preflight.json"); publication=load("data/live/publication_context.json")
    context={"market":load("data/live/market_snapshot.json"),"news":load("data/live/news_snapshot.json"),"preflight":preflight,"publication":publication,"memory":load("analytics/strategy_memory.json")}
    selected=preflight.get("selected_opportunity") or {}; instruction=os.getenv("TOPIC","").strip() or selected.get("instruction") or "Find the strongest evidence-based opportunity."
    prompt="Return ONLY JSON with research, critique, draft and visual_plan. Use only supplied evidence. Do not invent facts. The draft must be finished publication copy and include one story-specific question.\n"+instruction+"\n"+json.dumps(context,ensure_ascii=False)[:50000]
    try:
        raw,meta=nic_generate(prompt,"You are a senior evidence-based editorial system. Never invent facts. Return valid JSON.")
        result=parse(raw); mode="NIC"
    except Exception as exc:
        result={"research":{"summary":"Generation failed; downstream gates must block publication."},"critique":{"summary":str(exc)},"draft":{"post":"","quality_score":0,"editorial_style":"blocked"},"visual_plan":{"type":"none","use_visual":False}}; meta={}; mode="BLOCKED"
    research=normalize(result.get("research")); critique=normalize(result.get("critique")); draft=normalize(result.get("draft")); visual=normalize(result.get("visual_plan"))
    draft["generation_mode"]=mode; draft["publication_status"]="DRAFT_ONLY_NOT_PUBLISHED"; draft.setdefault("quality_score",0); draft.setdefault("content_category",selected.get("category") or "market_opportunity")
    if not draft.get("post") and draft.get("text"): draft["post"]=str(draft["text"]).strip()
    allowed={"candlestick_chart","market_bar_chart","market_comparison","market_range_chart","news_timeline","text_card","none"}
    if visual.get("type") not in allowed: visual={"type":"none","use_visual":False}
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"model":meta.get("model"),"provider":meta.get("provider"),"research":research,"critique":critique,"draft":draft,"visual_plan":visual,"nic_decision_contract":decision_contract(preflight,publication,research,critique,draft,visual),"status":"DRAFT_ONLY_NOT_PUBLISHED","generation_mode":mode}
    slug=re.sub(r"[^a-z0-9]+","-",str(research.get("strongest_signal") or selected.get("category") or "market-opportunity").lower()).strip("-")[:80] or "market-opportunity"
    out=OUTPUT_DIR/f"{slug}-multi-agent.json"; out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"report":str(out.relative_to(ROOT)),"quality_score":draft.get("quality_score",0),"generation_mode":mode,"visual_type":visual.get("type","none")},indent=2))

if __name__=="__main__": main()
