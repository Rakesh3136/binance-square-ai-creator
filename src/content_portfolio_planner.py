"""Bounded editorial portfolio planner with thesis follow-up integration.

The planner is the hand-off point between opportunity routing and publication.
NIC 19 is invoked here so the canonical workflow cannot bypass editorial memory
by forgetting to call the guard after planning.
"""
from __future__ import annotations
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/"analytics/publication_log.jsonl"; OUT=ROOT/"data/live/content_portfolio_plan.json"
FOLLOW_UP=ROOT/"data/live/thesis_follow_up_opportunities.json"; MEMORY=ROOT/"data/live/thesis_memory.json"; NIC_OS=ROOT/"data/live/nic_monetization_contract.json"
ROUTING=ROOT/"data/live/signal_first_routing.json"
WINNING_DNA=ROOT/"data/live/nic_winning_post_dna.json"
TREATMENTS=("market_setup","data_investigation","news_impact","asset_comparison","contrarian_thesis","outcome_accountability","weekly_synthesis")
CATEGORY_MAP={"technical_setup":"market_setup","capital_flow_long":"market_setup","capital_flow_short":"market_setup","flow":"market_setup","top_gainers":"market_setup","top_losers":"market_setup","high_volatility":"market_setup","volume_leaders":"data_investigation","data_surprise":"data_investigation","comparison":"asset_comparison","breaking_news":"news_impact","news_and_macro":"news_impact","research_insight":"data_investigation","market_mechanism":"data_investigation","education":"data_investigation","creator_signal_outcome":"outcome_accountability","follow_up":"outcome_accountability"}
NIC_LANE_CONTRACTS={"market_setup":"Chart-first conditional setup: evidence -> decision level -> confirmation -> invalidation; never force a trade call.","data_investigation":"Investigate one unusual relationship/anomaly using supplied evidence and explain the practical reader takeaway.","news_impact":"Use one fresh verified event, explain the supplied market mechanism, then identify what observable response would validate the interpretation.","asset_comparison":"Compare only evidence-supported assets; explain a concrete trade-off or relative-strength difference without inventing the second asset.","contrarian_thesis":"Challenge the obvious interpretation with supplied contrary evidence and define exactly what would falsify the thesis.","outcome_accountability":"Follow a prior thesis only when fresh evidence exists; state what changed, what held, and the next measurable test.","weekly_synthesis":"Synthesize verified observations from the week, separate knowns from unknowns, and define one next test."}

def refresh_thesis_bridge():
    """Refresh lightweight thesis telemetry from this cycle's ledger.
    It never publishes, trades, selects an asset, or bypasses downstream gates.
    """
    for script in ("src/thesis_memory_engine.py","src/thesis_follow_up_engine.py"):
        result=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,text=True,capture_output=True)
        if result.returncode!=0:
            print(result.stdout); print(result.stderr)
            raise RuntimeError(f"NIC thesis bridge failed: {script}")

def load_recent():
    if not LOG.exists(): return []
    rows=[]
    for line in LOG.read_text(encoding="utf-8").splitlines()[-40:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and str(x.get("status") or "").upper() in {"PUBLISHED_AUTONOMOUSLY","PUBLISHED_VERIFIED_BY_API_RESPONSE","VERIFIED_PUBLISHED","PUBLISHED_SUBMITTED_504"}: rows.append(x)
        except Exception: pass
    return rows[-20:]

def load_follow_ups():
    try:
        data=json.loads(FOLLOW_UP.read_text(encoding="utf-8"))
        rows=data.get("opportunities",[]) if isinstance(data,dict) else []
        return [x for x in rows if isinstance(x,dict) and x.get("eligibility")=="REQUIRES_NEW_VERIFIED_EVIDENCE_AND_MATERIALLY_NEW_PAYOFF"]
    except Exception: return []

def category(row):
    for k in ("category","story_lane","lane","content_category"):
        v=str(row.get(k) or "").strip().lower()
        if v:return v
    return ""

def run_nic19_guard():
    """Make NIC19 authoritative at the exact producer/consumer boundary."""
    try:
        import content_portfolio_guard
        rc=content_portfolio_guard.main()
        guard=json.loads((ROOT/"data/live/content_portfolio_guard.json").read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"NIC19 editorial-memory guard failed closed: {exc}") from exc
    try:
        routing=json.loads(ROUTING.read_text(encoding="utf-8"))
    except Exception:
        routing={}
    upstream=bool(routing.get("publish",False))
    allowed=bool(guard.get("publish",False))
    # NIC 19 is the final editorial-cadence authority. The signal-first
    # router remains an upstream qualification/input layer, not the publisher
    # gate. A valid NIC 19 selection may therefore proceed even when the
    # earlier router had no publish decision.
    routing["upstream_publish_decision"]=upstream
    routing["nic19_editorial_memory"]=guard
    routing["publish"]=allowed
    routing["decision_source"]="NIC19_EDITORIAL_MEMORY"
    routing["decision_reason"]=guard.get("reason")
    routing["nic19_authoritative_publish_decision"]=allowed
    ROUTING.write_text(json.dumps(routing,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return guard

def main():
    dna_run=subprocess.run([sys.executable,str(ROOT/"src/nic_winning_post_dna.py")],cwd=ROOT,text=True,capture_output=True)
    if dna_run.returncode!=0:
        print(dna_run.stdout); print(dna_run.stderr)
        raise RuntimeError("NIC Winning-Post DNA failed; refusing stale editorial contract")
    try: winning_dna=json.loads(WINNING_DNA.read_text(encoding="utf-8"))
    except Exception as exc: raise RuntimeError(f"NIC Winning-Post DNA output unavailable: {exc}") from exc
    refresh_thesis_bridge()
    recent=load_recent(); follow_ups=load_follow_ups(); counts=Counter(CATEGORY_MAP.get(category(x),"") for x in recent)
    try:
        value=json.loads(NIC_OS.read_text(encoding="utf-8"))
        os_contract=value if isinstance(value,dict) else {}
    except Exception:
        os_contract={}
    os_lane=str(os_contract.get("content_lane") or "").strip().lower()
    selected=os_lane if os_lane in TREATMENTS else ("outcome_accountability" if follow_ups else min(TREATMENTS,key=lambda x:(counts[x],TREATMENTS.index(x))))
    selected_follow_up=follow_ups[0] if follow_ups and selected=="outcome_accountability" else None
    plan={"version":"2.1","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY","selected_treatment":selected,
          "content_lane":selected,"campaign_day":os_contract.get("campaign_day"),"lane_goal":os_contract.get("lane_goal") or NIC_LANE_CONTRACTS.get(selected),
          "content_format":os_contract.get("content_format"),"hook_type":os_contract.get("hook_type"),"visual_type":os_contract.get("visual_type"),
          "reader_payoff_type":os_contract.get("reader_payoff_type"),"experiment_id":os_contract.get("experiment_id"),
          "experiment_variable":os_contract.get("experiment_variable"),"experiment_treatment":os_contract.get("experiment_treatment"),
          "cycle_id":os_contract.get("cycle_id"),"recent_verified_publications":len(recent),"recent_treatment_counts":dict(counts),
          "thesis_follow_up":selected_follow_up,"thesis_follow_up_candidates":len(follow_ups),
          "winning_post_dna":{"status":winning_dna.get("status"),"verified_revenue_post_count":winning_dna.get("verified_revenue_post_count"),"editorial_contract":winning_dna.get("editorial_contract")},
          "principles":{"asset_selection_unchanged":True,"evidence_unchanged":True,"signal_first_unchanged":True,"quality_gates_authoritative":True,
                        "no_private_chain_of_thought":True,"world_news_requires_fresh_verified_source":True,"one_story_per_post":True,
                        "thesis_follow_up_requires_fresh_evidence":True,"nic_os_lane_is_editorial_only":True,
                        "experiment_lineage_must_survive_fallback":True,"nic19_editorial_memory_authoritative":True},
          "treatment_contracts":NIC_LANE_CONTRACTS}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    guard=run_nic19_guard()
    plan["nic19_editorial_memory"]={"publish":guard.get("publish"),"decision":guard.get("decision"),"reason":guard.get("reason"),"selected":guard.get("selected")}
    OUT.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(plan,indent=2,ensure_ascii=False))

if __name__=="__main__":main()