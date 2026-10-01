from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
from nic_model_router import generate as nic_generate, generate_specialist as nic_specialist

ROOT=Path(__file__).resolve().parents[1]
OUTPUT_DIR=ROOT/"data/reports"; OUTPUT_DIR.mkdir(parents=True,exist_ok=True)

EDITORIAL_RULES = r"""
NEWS MODE:
- If the selected lane is news-driven, distinguish the reported event from NIC's interpretation.
- Never turn an unverified headline, rumor, or social claim into a fact.
- Prefer primary/frozen evidence supplied in the context.

TECHNICAL MODE:
- Any technical claim must be tied to supplied market evidence such as price structure, volume, range, levels, trend, momentum, or other explicitly provided measurements.
- Do not invent indicators, support/resistance levels, targets, or numerical values.

EXACTLY ONE QUESTION RULE:
- The finished post must contain exactly ONE story-specific question.
- The question must arise from the actual thesis or uncertainty, not be generic engagement bait.

ANTI-SLOP PHRASES TO AVOID:
- Avoid generic filler, motivational clichés, empty market commentary, repeated hooks, unsupported certainty, fake urgency, and generic calls to action.
- Every paragraph must add concrete information or interpretation.

Return ONLY valid JSON:
- The model response must be one JSON object with research, critique, draft, and visual_plan.
- No markdown fence, preamble, or commentary outside the JSON object.

FINISHED-POST CONTRACT:
- draft.post must be finished publication copy, not notes or instructions.
- Use only supplied evidence and preserve uncertainty where evidence is incomplete.
- The post should be concise, original, useful, and materially different from recent content.
"""


def load(name):
    p=ROOT/name
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}

def normalize(v): return v if isinstance(v,dict) else ({"summary":v} if isinstance(v,str) else {})

def parse(text):
    text=re.sub(r"^\`\`\`(?:json)?\s*|\s*\`\`\`$","",str(text or "").strip())
    v=json.loads(text)
    if not isinstance(v,dict): raise ValueError("non-object response")
    return v

def decision_contract(preflight,publication,research,critique,draft,visual):
    selected=preflight.get("selected_opportunity") or {}
    return {"schema_version":"nic-decision-contract-1.2","created_at":datetime.now(timezone.utc).isoformat(),"authority":"AUTHORITATIVE_DOWNSTREAM_GATES","evidence":{"selected_symbol":publication.get("symbol") or selected.get("symbol"),"selected_lane":selected.get("category") or selected.get("reason")},"thesis":{"summary":research.get("summary"),"strongest_signal":research.get("strongest_signal"),"opportunity_score":research.get("opportunity_score"),"counterpoint":critique.get("summary")},"editorial":{"category":draft.get("content_category"),"experiment_id":draft.get("experiment_id"),"generation_mode":draft.get("generation_mode")},"visual":{"type":visual.get("type","none"),"use_visual":bool(visual.get("use_visual")),"provider":visual.get("provider"),"purpose":visual.get("purpose")},"quality":{"draft_quality_score":draft.get("quality_score"),"private_reasoning_exposed":False,"publication_status":"DRAFT_ONLY_NOT_PUBLISHED"},"hard_invariants":["verified_evidence_only","no_private_chain_of_thought_publication","no_unsupported_claims","no_duplicate_thesis","no_gate_bypass"]}

def main():
    preflight=load("data/live/editorial_preflight.json"); publication=load("data/live/publication_context.json")
    context={"market":load("data/live/market_snapshot.json"),"news":load("data/live/news_snapshot.json"),"preflight":preflight,"publication":publication,"memory":load("analytics/strategy_memory.json"),"wte_strategy":load("data/live/wte_high_level_intelligence.json"),"wte_7day":load("data/live/write_to_earn_7day_status.json")}
    selected=preflight.get("selected_opportunity") or {}; instruction=os.getenv("TOPIC","").strip() or selected.get("instruction") or "Find the strongest evidence-based opportunity."
    # Bind the actual editorial/craft contracts into the model prompt. Previously
    # these were generated upstream but only partially visible through preflight,
    # allowing the model to fall back to the older generic house style.
    script_director=preflight.get("script_director_4") or {}
    craft=load("data/live/nic_content_craft_9.json")
    portfolio={
        "lane": load("data/live/nic_monetization_contract.json").get("portfolio_lane"),
        "format": load("data/live/nic_monetization_contract.json").get("portfolio_format"),
        "hook_type": load("data/live/nic_monetization_contract.json").get("portfolio_hook_type"),
        "visual_type": load("data/live/nic_monetization_contract.json").get("portfolio_visual_type"),
        "reader_payoff_type": load("data/live/nic_monetization_contract.json").get("portfolio_reader_payoff_type"),
    }
    style_contract={
        "creator_archetype": script_director.get("creator_archetype"),
        "narrative_engine": script_director.get("narrative_engine"),
        "recommended_format": script_director.get("format"),
        "hook_candidates": script_director.get("hook_candidates",[]),
        "question": script_director.get("recommended_question"),
        "writing_contract": script_director.get("writing_contract",[]),
        "anti_template_rules": script_director.get("anti_template_rules",[]),
        "craft": craft.get("craft") or craft.get("contract") or craft.get("design") or {},
        "portfolio_slot": portfolio,
    }
    base_prompt=(EDITORIAL_RULES+
        "\nCURRENT EDITORIAL STYLE CONTRACT — THIS RUN:\n"+
        json.dumps(style_contract,ensure_ascii=False)[:30000]+
        "\nTASK:\n"+instruction+
        "\nEVIDENCE:\n"+json.dumps(context,ensure_ascii=False)[:50000])
    deep_research={}; research_meta={}
    try:
        deep_prompt="""Act as the NIC deep-research specialist. Analyze the supplied market/news/editorial evidence before another model writes the post.
Return ONLY JSON with: verified_observations, cross_asset_links, causal_mechanisms, contradictions, missing_evidence, alternative_hypotheses, disconfirming_tests, research_priority, synthesis.
Do not invent facts, prices, events, sources, or certainty. Treat every hypothesis as a hypothesis. Focus on what can be verified from the supplied evidence and what would falsify the leading interpretation.
Do not reveal private chain-of-thought; provide concise public-safe evidence and conclusions only.
""" + "\nTASK:\n" + instruction + "\nEVIDENCE:\n" + json.dumps(context,ensure_ascii=False)[:50000]
        raw_research,research_meta=nic_specialist(deep_prompt,"You are NIC's deep-research specialist. Be rigorous, evidence-first, adversarial, and explicit about uncertainty.","nemotron")
        deep_research=parse(raw_research)
    except Exception as exc:
        research_meta={"provider":"nemotron","status":"unavailable","error":type(exc).__name__}
    enriched_context=dict(context)
    if deep_research:
        enriched_context["nemotron_deep_research"]=deep_research
    prompt=base_prompt+"\nHIGH-LEVEL WTE STRATEGY (advisory only; deterministic gates remain authoritative):\n"+json.dumps(enriched_context.get("wte_strategy",{}),ensure_ascii=False)[:16000]+"\nWTE 7-DAY STATE:\n"+json.dumps(enriched_context.get("wte_7day",{}),ensure_ascii=False)[:8000]+"\nNEMOTRON DEEP-RESEARCH (use as analysis input, never as permission to invent facts):\n"+json.dumps(deep_research,ensure_ascii=False)[:30000]
    try:
        raw,meta=nic_generate(prompt,"You are a senior evidence-based editorial system. Apply every EDITORIAL_RULES requirement, use the supplied deep research as an input, verify it against the frozen evidence, never invent facts, and return valid JSON.")
        result=parse(raw); mode="NIC"
    except Exception as exc:
        result={"research":{"summary":"Generation failed; downstream gates must block publication."},"critique":{"summary":str(exc)},"draft":{"post":"","quality_score":0,"editorial_style":"blocked"},"visual_plan":{"type":"none","use_visual":False}}; meta={}; mode="BLOCKED"
    research=normalize(result.get("research")); critique=normalize(result.get("critique")); draft=normalize(result.get("draft")); visual=normalize(result.get("visual_plan"))
    if deep_research:
        research["deep_research_provider"]="nemotron"
        research["deep_research_status"]="success"
        research["deep_research_summary"]=deep_research.get("synthesis") or deep_research.get("research_priority")
    else:
        research["deep_research_provider"]="nemotron"
        research["deep_research_status"]=research_meta.get("status","unavailable")
    draft["generation_mode"]=mode; draft["publication_status"]="DRAFT_ONLY_NOT_PUBLISHED"; draft.setdefault("quality_score",0); draft.setdefault("content_category",selected.get("category") or "market_opportunity")
    if not draft.get("post") and draft.get("text"): draft["post"]=str(draft["text"]).strip()
    allowed={"candlestick_chart","market_bar_chart","market_comparison","market_range_chart","news_timeline","text_card","none"}
    if visual.get("type") not in allowed: visual={"type":"none","use_visual":False}
    report={"generated_at":datetime.now(timezone.utc).isoformat(),"model":meta.get("model"),"provider":meta.get("provider"),"research":research,"deep_research":deep_research,"deep_research_meta":research_meta,"critique":critique,"draft":draft,"visual_plan":visual,"nic_decision_contract":decision_contract(preflight,publication,research,critique,draft,visual),"status":"DRAFT_ONLY_NOT_PUBLISHED","generation_mode":mode}
    slug=re.sub(r"[^a-z0-9]+","-",str(research.get("strongest_signal") or selected.get("category") or "market-opportunity").lower()).strip("-")[:80] or "market-opportunity"
    out=OUTPUT_DIR/f"{slug}-multi-agent.json"; out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"report":str(out.relative_to(ROOT)),"quality_score":draft.get("quality_score",0),"generation_mode":mode,"visual_type":visual.get("type","none"),"deep_research_provider":"nemotron","deep_research_status":research.get("deep_research_status")},indent=2))

if __name__=="__main__": main()
