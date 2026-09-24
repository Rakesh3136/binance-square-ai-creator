"""NIC Autonomous Knowledge Acquisition v1.

Keyless curiosity/research planner. It identifies knowledge gaps from the
current NIC state, turns them into bounded research questions, records what
was already investigated, and prioritizes the next questions. It never
invents evidence and never overrides publication/safety gates.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_knowledge_acquisition.json"
REPORT=INTEL/"nic_knowledge_acquisition_report.json"
MEMORY=LIVE/"nic_knowledge_memory.json"

TARGETS=[
 ("crypto_fundamentals","How do BTC, ETH, stablecoins and major crypto sectors differ in economic function and risk?"),
 ("chart_microstructure","How do price structure, volume, volatility and derivatives positioning interact on a live chart?"),
 ("global_liquidity","How do rates, yields, USD, credit and liquidity conditions transmit into risk assets?"),
 ("commodity_transmission","Through which sectors and macro channels can oil, gold and industrial commodities affect crypto?"),
 ("cross_asset_lead_lag","Which cross-asset moves consistently precede or follow BTC in the current regime?"),
 ("stablecoin_liquidity","What verified stablecoin supply, flows or exchange-liquidity measures can proxy crypto liquidity?"),
 ("derivatives_positioning","How should funding, open interest, basis and liquidations be interpreted without treating them as direction guarantees?"),
 ("market_breadth","What do BTC dominance, breadth, sector dispersion and relative strength say about broad versus idiosyncratic crypto moves?"),
 ("macro_surprises","How do actual economic releases differ from expectations and how does that distinction affect market interpretation?"),
 ("geopolitical_transmission","How do wars, sanctions, trade restrictions and energy shocks transmit through commodities, FX, rates and crypto?"),
 ("token_specific_risk","What tokenomics, unlocks, listings, delistings, protocol activity and catalysts explain coin-specific behavior?"),
 ("financial_history","Which historical regimes resemble the current regime and where did apparently similar signals fail?"),
 ("statistics","How can NIC distinguish correlation, causation, selection bias, regime change and small-sample noise?"),
 ("source_literacy","Which claims require primary sources and how should conflicting sources be reconciled?"),
 ("language_communication","How can financial explanations stay precise, professional, concise and uncertainty-calibrated?"),
]

def load(p,default):
    try:
        if not p.exists(): return default
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,type(default)) else default
    except Exception: return default

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def main():
    finance=load(LIVE/"nic_financial_market_intelligence.json",{})
    self_train=load(LIVE/"creator_self_training.json",{})
    route=load(LIVE/"content_master_route.json",{})
    old=load(MEMORY,{"completed":{},"attempts":{}})
    completed=old.get("completed") if isinstance(old.get("completed"),dict) else {}
    attempts=old.get("attempts") if isinstance(old.get("attempts"),dict) else {}

    # Existing capabilities reduce urgency; missing outputs increase it.
    missing=[]
    required=[
        ("financial_intelligence",LIVE/"nic_financial_market_intelligence.json"),
        ("cross_asset_impact",LIVE/"cross_asset_impact.json"),
        ("capital_flow",LIVE/"capital_flow_intelligence.json"),
        ("content_master",LIVE/"content_master_route.json"),
    ]
    for name,path in required:
        if not path.exists(): missing.append(name)

    candidates=[]
    for domain,question in TARGETS:
        key=digest(domain+"|"+question)
        attempts[key]=int(attempts.get(key,0))+1
        if key not in completed:
            priority=100
            if domain in {"cross_asset_lead_lag","global_liquidity","derivatives_positioning","commodity_transmission"}: priority+=15
            if domain in {"crypto_fundamentals","chart_microstructure","language_communication"}: priority+=10
            candidates.append({"id":key,"domain":domain,"question":question,"priority":priority,"status":"RESEARCH_CANDIDATE"})
    candidates.sort(key=lambda x:(-x["priority"],x["domain"]))

    # A missing capability becomes an immediate research/build task.
    for m in missing:
        q={"financial_intelligence":"Repair/restore the financial intelligence knowledge layer.",
           "cross_asset_impact":"Identify the missing verified cross-asset impact pipeline.",
           "capital_flow":"Identify the missing verified capital-flow pipeline.",
           "content_master":"Identify why Content Master routing is unavailable and restore it."}.get(m)
        if q:
            candidates.insert(0,{"id":digest("missing|"+m),"domain":"capability_repair","question":q,"priority":150,"status":"CAPABILITY_GAP"})

    selected=candidates[:8]
    state={
        "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"ACTIVE","mode":"CONTINUOUS_AUTONOMOUS_RESEARCH",
        "capabilities":{"financial_intelligence_ready":bool(finance),"self_training_ready":bool(self_train),"content_master_ready":bool(route)},
        "knowledge_gaps":selected,
        "research_policy":{
            "source_order":["primary/official","high_quality_financial","reputable_news","secondary_research","community"],
            "cross_check_sources":2,
            "minimum_repeated_observations_for_rule":3,
            "hypothesis_before_rule":True,
            "store_failed_hypotheses":True,
            "allow_unknown":True,
            "no_automatic_trade_prediction":True,
            "no_override_of_publication_gates":True,
        },
        "growth_loop":["identify_gap","form_question","research","cross_check","test","store_evidence","revisit","promote_or_invalidate"],
        "next_training":selected,
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    memory={"version":"1.0","updated_at":state["generated_at"],"completed":completed,"attempts":attempts,
            "policy":"Continuous knowledge acquisition; evidence must be verified before promotion."}
    MEMORY.write_text(json.dumps(memory,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"1.0","status":"ACTIVE","selected_questions":len(selected),
        "domains":[x["domain"] for x in selected],"continuous":True,"unknowns_allowed":True},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"ACTIVE","selected_questions":len(selected),"domains":[x["domain"] for x in selected]}))

if __name__=="__main__": raise SystemExit(main())
