"""High-level Write-to-Earn strategist."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; AN=ROOT/"analytics"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"wte_high_level_intelligence.json"; REPORT=INTEL/"wte_high_level_intelligence_report.json"
def load(name, default=None):
    p=ROOT/name
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,type(default)) else (default if default is not None else {})
    except Exception: return default if default is not None else {}
def rows(name,n=120):
    p=ROOT/name
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            v=json.loads(line)
            if isinstance(v,dict): out.append(v)
        except Exception: pass
    return out
def num(v,d=0.0):
    try:return float(v)
    except Exception:return d
def sym(v): return re.sub(r"[^A-Z0-9]","",str(v or "").upper().replace("USDT","").replace("$",""))[:15]
def clamp(v): return round(max(0,min(100,num(v))),2)
def fallback(candidate,market,audience,wte,pubs):
    symbol=sym(candidate.get("symbol")); ranker=num(candidate.get("ranker_score") or candidate.get("score")); signal=num(candidate.get("content_signal_score")); recent_same=sum(1 for x in pubs if sym(x.get("symbol"))==symbol)
    return {"selected_asset":symbol,"thesis_angle":"Explain one non-obvious mechanism connecting the verified observation to why the asset matters now.","reader_payoff":"Give one concrete observation, one practical implication, and one falsification condition.","evidence_priority":["fresh market structure","cross-checking context","explicit uncertainty"],"counter_case":"State what would make the thesis wrong before publication.","question_design":"End with exactly one thesis-specific question, not generic engagement bait.","visual_purpose":"Use a chart only when it adds a readable relationship, level, flow or comparison that text alone cannot convey.","reader_action_path":"Make the relevant asset easy to inspect through the verified primary cashtag or trading widget; never pressure a trade.","scores":{"evidence_strength":clamp(40+ranker*.5+min(15,signal*.15)),"novelty":clamp(100-recent_same*18),"reader_action_fit":clamp(50+20*bool(wte.get("eligible"))+20*bool(wte.get("has_primary_cashtag") or wte.get("verified_widget"))),"audience_fit":65 if audience.get("observed_patterns") else 55,"opportunity_strength":clamp(ranker)},"risk_flags":[f"recent_same_asset_count={recent_same}"] if recent_same else [],"method":"deterministic_fallback"}
def parse_json_object(raw):
    text=str(raw or "").strip()
    text=re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.I)
    text=re.sub(r"\s*```\s*$", "", text)
    try:
        v=json.loads(text)
        if isinstance(v,dict): return v
    except Exception: pass
    start=text.find("{"); end=text.rfind("}")
    if start>=0 and end>start:
        try:
            v=json.loads(text[start:end+1])
            if isinstance(v,dict): return v
        except Exception: pass
    raise ValueError("Nemotron response did not contain a valid JSON object")
def main():
    candidate=(load("data/live/editorial_preflight.json",{}) or {}).get("selected_opportunity") or {}; market=load("data/live/market_snapshot.json",{}); research=load("data/live/original_research.json",{}); audience=load("data/live/creator_22_0_audience_board.json",{}); wte=load("data/live/write_to_earn_eligibility.json",{}); plan=load("data/live/write_to_earn_7day_plan.json",{}); status=load("data/live/write_to_earn_7day_status.json",{}); prediction=load("data/live/nic_prediction_engine.json",{}); memory=load("analytics/strategy_memory.json",{}); pubs=rows("analytics/publication_log.jsonl")
    context={"selected_opportunity":candidate,"market_snapshot":market,"original_research":research,"audience_board":audience,"wte_eligibility":wte,"wte_7day_plan":plan,"wte_7day_status":status,"prediction_engine":prediction,"strategy_memory":memory,"recent_publications":pubs[-30:],"guardrails":{"no_revenue_inference":True,"no_fake_engagement":True,"no_trade_pressure":True,"no_private_chain_of_thought":True}}
    brief=fallback(candidate,market,audience,wte,pubs); provider="deterministic"; model=None; external_status="not_attempted"
    key=os.getenv("NEMOTRON_API_KEY","").strip()
    if key:
        try:
            from nic_model_router import generate_specialist
            prompt="""Act as the chief strategic intelligence layer for a Binance Square creator. Synthesize the supplied evidence into a concise public-safe strategy brief. Optimize information value, originality, reader usefulness, native asset attribution and seven-day content diversity. Do not optimize fake clicks or guaranteed earnings. Do not invent facts, trades, rewards, prices, sources or certainty. Do not reveal private chain-of-thought. Return ONLY a JSON object with: selected_asset, thesis_angle, reader_payoff, evidence_priority, cross_asset_context, counter_case, question_design, visual_purpose, reader_action_path, risks, experiment_variable, scores, synthesis. scores must contain numeric 0-100 fields: evidence_strength, novelty, reader_action_fit, audience_fit, opportunity_strength.\n\n"""+json.dumps(context,ensure_ascii=False)[:60000]
            raw,meta=generate_specialist(prompt,"You are NIC's chief strategic research synthesizer. Evidence-first, adversarial, concise, public-safe.","nemotron")
            candidate_brief=parse_json_object(raw); brief.update(candidate_brief); provider=meta.get("provider","nemotron"); model=meta.get("model"); external_status="success"
        except Exception as exc: external_status=type(exc).__name__
    brief.update({"version":"WTE-HLI-1.1","generated_at":datetime.now(timezone.utc).isoformat(),"campaign_day":status.get("campaign_day"),"wte_reason":wte.get("reason"),"wte_attribution_ready":bool(wte.get("has_primary_cashtag") or wte.get("verified_widget")),"provider":provider,"model":model,"external_status":external_status,"authority":"ADVISORY_INPUT_ONLY","hard_invariants":["fresh_evidence_only","no_private_chain_of_thought","no_revenue_inference","no_fake_engagement","no_gate_bypass"]})
    OUT.parent.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(brief,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); REPORT.write_text(json.dumps({"version":"WTE-HLI-1.1","generated_at":brief["generated_at"],"provider":provider,"external_status":external_status,"scores":brief.get("scores",{}),"selected_asset":brief.get("selected_asset"),"experiment_variable":brief.get("experiment_variable")},indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps({"status":"READY","provider":provider,"external_status":external_status,"selected_asset":brief.get("selected_asset"),"scores":brief.get("scores",{})},indent=2))
if __name__=="__main__": main()
