"""NIC Content Craft Intelligence 9.0 — story-specific editorial design.

Turns the authoritative Story Discovery result into a bounded craft contract for
candidate generation. It chooses narrative shape, hook, evidence order, reader
payoff, question type and visual proof while actively resisting template reuse.
It never exposes private reasoning or invents facts.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
DISCOVERY=LIVE/"nic_story_discovery.json"; PORTFOLIO=LIVE/"nic_adaptive_content_portfolio_8.json"
MONETIZATION=LIVE/"nic_monetization_contract.json"; CONTEXT=LIVE/"publication_context.json"
RECENT=LIVE/"publication_log.jsonl"
OUT=LIVE/"nic_content_craft_9.json"; REPORT=INTEL/"nic_content_craft_9_report.json"

GENERIC_HOOKS=(
    "that matters because","here's what matters","here is what matters",
    "in today's market","the market is watching","is moving, but",
    "could be important","let's look at",
)
FORBIDDEN_INTERNAL=("attention score","quality score","experiment id","generation_mode",
                    "content_lane","reader_payoff_type","hook_type","campaign day","cycle id")
TRADE_PRESSURE=("buy now","sell now","guaranteed","guarantee","can't lose","must buy","must sell","urgent")

ARCHETYPES={
 "market_setup":("conditional_thesis","observation→evidence→trigger→invalidation→implication","confirmation_checkpoint","structure_or_trigger_chart"),
 "data_investigation":("data_surprise","anomaly→comparison→mechanism→limitation→test","measurable_data_test","relationship_or_volume_chart"),
 "breaking_news":("event_reaction","verified_event→time_context→transmission→asset→confirmation","market_reaction_checkpoint","event_timeline_or_reaction_chart"),
 "world_macro":("transmission_chain","macro_fact→crypto_channel→exposure→second_order→falsifier","macro_transmission_checkpoint","cross_asset_or_transmission_visual"),
 "research_lesson":("research_finding","finding→evidence→meaning→takeaway→limitation","evidence_boundary","evidence_comparison_chart"),
 "education":("mechanism_myth","mechanism→current_example→misconception→takeaway","observable_example_test","mechanism_diagram_or_example_chart"),
 "contrarian_thesis":("evidence_against_consensus","consensus→contrary_evidence→alternative→falsifier→risk","falsifier_checkpoint","evidence_vs_consensus_chart"),
 "follow_up":("thesis_update","previous_thesis→observed_outcome→what_changed→updated_view→checkpoint","outcome_checkpoint","before_after_chart"),
 "outcome_accountability":("call_vs_result","prior_call→verified_result→lesson→changed_rule→next_test","accountability_checkpoint","call_vs_actual_chart"),
 "weekly_synthesis":("pattern_synthesis","2_3_observations→common_thread→lesson→watchlist","next_week_checkpoint","multi_observation_comparison"),
 "nic_learning_note":("observable_system_lesson","recorded_outcome→observable_lesson→system_change→next_test","next_test_checkpoint","outcome_change_visual"),
}
DEFAULT=ARCHETYPES["market_setup"]

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def recent_texts(limit=20):
    if not RECENT.exists(): return []
    out=[]
    for line in RECENT.read_text(encoding="utf-8",errors="ignore").splitlines()[-limit:]:
        try:
            x=json.loads(line)
        except Exception: continue
        if isinstance(x,dict):
            t=str(x.get("text") or x.get("post") or x.get("content") or "").strip()
            if t: out.append(t)
    return out

def collision_score(text,a,b):
    ta=set(re.findall(r"[a-z0-9$]{3,}",text.lower()))
    tb=set(re.findall(r"[a-z0-9$]{3,}",a.lower()))
    tc=set(re.findall(r"[a-z0-9$]{3,}",b.lower()))
    if not ta or not tb: return 0.0
    return round(len(ta&tb)/max(1,len(ta)),3), round(len(ta&tc)/max(1,len(tc)),3)

def main():
    discovery=load(DISCOVERY); portfolio=load(PORTFOLIO); monetization=load(MONETIZATION); context=load(CONTEXT)
    if discovery.get("status")!="DISCOVERED": raise SystemExit("Craft 9: Story Discovery is not DISCOVERED")
    lane=str(discovery.get("selected_lane") or "").lower()
    if lane not in ARCHETYPES: lane="market_setup"
    evidence=[x for x in discovery.get("evidence",[]) if isinstance(x,dict) and str(x.get("text") or "").strip()]
    if not evidence: raise SystemExit("Craft 9: no evidence supplied by Story Discovery")
    asset=str(discovery.get("asset") or context.get("symbol") or "").upper().replace("USDT","").replace("$","").strip()
    if not asset: raise SystemExit("Craft 9: authoritative asset missing")

    archetype,order,checkpoint,visual=ARCHETYPES[lane]
    evidence_types=[]
    for e in evidence[:8]:
        field=str(e.get("field") or "")
        if field not in evidence_types: evidence_types.append(field)

    recent=recent_texts()
    recent_openers=[x.split("\n",1)[0].strip() for x in recent[:12]]
    recent_fingerprints=[]
    for x in recent[:12]:
        recent_fingerprints.append(hashlib.sha256(re.sub(r"\$?[A-Z0-9]{2,15}","$ASSET",x.upper()).encode()).hexdigest()[:10])

    # Prefer a hook that is anchored to the strongest supplied evidence rather
    # than a reusable ticker/price opener.
    hook_map={
      "data_investigation":"lead with the unexpected measured relationship",
      "breaking_news":"lead with the verified event and its market transmission",
      "world_macro":"lead with the macro change that reaches this asset through a specific channel",
      "research_lesson":"lead with the research finding that changes the reader's model",
      "contrarian_thesis":"lead with the evidence that conflicts with the common interpretation",
      "follow_up":"lead with what actually happened versus the prior thesis",
      "outcome_accountability":"lead with the verified result of the prior call",
      "education":"lead with the mechanism that explains the current example",
      "weekly_synthesis":"lead with the recurring pattern across the strongest observations",
      "nic_learning_note":"lead with an observable outcome and the lesson it supports",
      "market_setup":"lead with the specific condition that makes this setup different",
    }
    question_map={
      "data_investigation":"ask which measurable relationship should confirm or weaken the finding",
      "breaking_news":"ask what observable market reaction would confirm the transmission",
      "world_macro":"ask which asset/metric should confirm the proposed transmission",
      "research_lesson":"ask what evidence would strengthen or overturn the finding",
      "contrarian_thesis":"ask what evidence would falsify the alternative explanation",
      "follow_up":"ask which checkpoint should decide whether the updated view remains valid",
      "outcome_accountability":"ask what next measurable test should govern the changed rule",
      "education":"ask which observable example best tests the mechanism",
      "weekly_synthesis":"ask which watchlist signal would confirm the shared pattern",
      "nic_learning_note":"ask what measurable result should test the system change",
      "market_setup":"ask what observable condition should confirm or invalidate the thesis",
    }
    payoff_map={
      "data_investigation":"give the reader a relationship they can independently inspect",
      "breaking_news":"give the reader a transmission chain they can verify",
      "world_macro":"give the reader a causal path from macro fact to asset exposure",
      "research_lesson":"give the reader a useful finding plus its limitation",
      "contrarian_thesis":"give the reader a falsifiable alternative, not a prediction",
      "follow_up":"give the reader an accountable update to an earlier thesis",
      "outcome_accountability":"give the reader a verified lesson and next test",
      "education":"give the reader a mechanism they can apply to a live example",
      "weekly_synthesis":"give the reader a compact pattern and concrete watchlist",
      "nic_learning_note":"give the reader an observable system lesson",
      "market_setup":"give the reader a conditional decision map without trade pressure",
    }
    payload={
      "version":"9.0","status":"READY","created_at":datetime.now(timezone.utc).isoformat(),
      "craft_id":"craft9-"+hashlib.sha256(f"{discovery.get('story_id')}|{lane}|{asset}|{evidence_types}".encode()).hexdigest()[:16],
      "story_id":discovery.get("story_id"),"asset":asset,"lane":lane,"archetype":archetype,
      "hook_type":hook_map[lane],"evidence_order":order,"required_evidence_fields":evidence_types[:5],
      "primary_claim_rule":"one evidence-backed claim; do not broaden beyond supplied evidence",
      "mechanism_rule":"explain the causal bridge before any scenario implication",
      "specificity_rule":"use concrete supplied facts and precise verbs; avoid adjectives as evidence",
      "paragraph_rule":"one idea per paragraph; vary sentence length and rhythm",
      "reader_payoff":payoff_map[lane],"question_type":question_map[lane],
      "checkpoint_type":checkpoint,"visual_proof_type":visual,
      "visual_rule":"the visual must prove the selected story, not merely decorate the ticker",
      "opening_rule":"story-specific hook tied to observed evidence; never generic ticker/market filler",
      "question_rule":"exactly one measurable, story-specific question at the end",
      "length_rule":"final reader copy <=740 characters",
      "differentiation":{
        "recent_publication_count":len(recent),
        "recent_openers":recent_openers[:8],
        "asset_swap_test_required":True,
        "structure_collision_threshold":0.72,
        "avoid_repeating_recent_fingerprint":recent_fingerprints[:8],
      },
      "forbidden_reader_content":[*FORBIDDEN_INTERNAL,*TRADE_PRESSURE,"private reasoning","hidden chain-of-thought"],
      "portfolio_signal":{"selected_lane":lane,"target_share":next((x.get("target_share") for x in portfolio.get("allocations",[]) if x.get("lane")==lane),None)},
      "evidence":evidence[:8],
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"9.0","status":"READY","craft_id":payload["craft_id"],"lane":lane,"asset":asset,"evidence_count":len(evidence),"output":str(OUT.relative_to(ROOT))},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","version":"9.0","craft_id":payload["craft_id"],"lane":lane,"asset":asset}))

if __name__=="__main__": main()
