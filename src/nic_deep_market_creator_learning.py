"""NIC Deep Market + Binance Square Creator Learning Orchestrator."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_deep_learning_contract.json"
REPORT=INTEL/"nic_deep_learning_report.json"
MEMORY=INTEL/"nic_deep_learning_memory.json"

MARKET=[
("market_structure","Regimes, trend/range transitions, volatility, structure and invalidation"),
("liquidity_microstructure","Spread, depth, slippage, volume quality, funding, open interest and liquidations"),
("cross_asset_macro","Rates, yields, USD, equities, commodities and verified crypto transmission"),
("token_fundamentals","Utility, unlocks, emissions, governance, catalysts and project-specific risks"),
("event_risk","Listings, unlocks, incidents and timestamped source verification"),
("forecast_science","Base rates, calibration, out-of-sample tests, costs and matched benchmarks")]
CREATORS=[
("creator_originality","Distinct thesis and evidence; do not copy creator identity or signature wording"),
("reader_value","Specific takeaway, mechanism, uncertainty and falsifiable follow-up"),
("format_experimentation","Compare explainers, investigations, data surprises and event reactions"),
("visual_truth","Match chart symbol, exchange, timeframe, timestamps and text levels"),
("audience_learning","Separate reach and engagement from verified Write-to-Earn attribution"),
("platform_compliance","Current official rules, disclosures, attribution and eligibility")]
SOURCE_RULES={"priority":["official/primary","reputable data/research","reputable journalism","community observation"],"independent_sources_for_material_claim":2,"preserve_url_timestamp_and_excerpt_hash":True,"separate_fact_inference_hypothesis":True,"store_disconfirming_evidence":True,"unverified_creator_earnings_are_not_facts":True}
PROMOTION={"minimum_independent_observations":3,"require_out_of_sample_test_for_predictive_rule":True,"require_costs_and_matched_benchmarks":True,"require_regime_and_asset_scope":True,"insufficient_evidence_action":"WAIT_OR_RESEARCH"}
GUARDRAILS={"trade_authorized":False,"publication_authorized":False,"live_orders_enabled":False,"learning_may_bypass_gates":False,"creator_examples_are_benchmarks_not_templates":True,"views_are_not_revenue":True,"revenue_requires_verified_write_to_earn_evidence":True}
REQUIRED_INPUTS=("market_intelligence","square_style","knowledge_acquisition","content_craft","forecast_profitability")
READY_STATUSES={"READY","SUCCESS","SUCCEEDED","COMPLETE","COMPLETED","OK","PASS","PASSED","PRESENT","CURRENT"}

def now(): return datetime.now(timezone.utc).isoformat()
def read(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,(dict,list)) else {}
    except (OSError,json.JSONDecodeError): return {}
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def validate_artifacts(artifacts):
    """Return current-run evidence gaps; explicit failed/stale statuses never count as present."""
    gaps=[]
    for key in REQUIRED_INPUTS:
        value=artifacts.get(key)
        if not isinstance(value,(dict,list)) or not value:
            gaps.append(key+"_artifact_missing")
            continue
        if isinstance(value,dict) and "status" in value:
            status=str(value.get("status","")).strip().upper()
            if status not in READY_STATUSES:
                gaps.append(key+"_artifact_status_"+(status.lower() or "empty"))
    return sorted(set(gaps))
def build_contract(artifacts, previous=None):
    previous=previous if isinstance(previous,dict) else {}
    gaps=validate_artifacts(artifacts)
    inputs={}
    for key,value in artifacts.items():
        status=(str(value.get("status","PRESENT")).strip().upper() if isinstance(value,dict) and value else ("PRESENT" if value else "MISSING"))
        inputs[key]={"present":bool(value),"status":status,"sha256":digest(value)}
    result={"schema":"NIC-DEEP-LEARNING-1.1","generated_at":now(),"status":"LEARNING_WITH_GAPS" if gaps else "LEARNING_INPUTS_PRESENT","mission":"Build evidence-grounded market understanding and original, useful Binance Square creator capability; measure before promoting beliefs.","domains":[{"domain":n,"objective":o,"mode":"RESEARCH_AND_MEASURE","promotion":"EVIDENCE_REQUIRED","failure_policy":"KEEP_UNCERTAIN_AND_RECORD_GAP"} for n,o in MARKET+CREATORS],"source_rules":SOURCE_RULES,"promotion_rules":PROMOTION,"guardrails":GUARDRAILS,"inputs":inputs,"known_gaps":gaps,"previous_run_known_gaps":sorted(set(str(x) for x in previous.get("known_gaps",[]) if isinstance(x,str))),"next_actions":["refresh primary-source market and platform evidence","separate facts from inference and competing hypotheses","measure original reader payoff rather than copying creators","test forecasts chronologically after costs against cash, BTC and matched counterfactuals","record failed hypotheses and negative outcomes","keep publishing paused until quality gates pass production verification"]}
    result["contract_sha256"]=digest(result)
    return result
def main():
    artifacts={"market_intelligence":read(LIVE/"nic_financial_market_intelligence.json"),"square_style":read(INTEL/"square_style_intelligence.json"),"knowledge_acquisition":read(LIVE/"nic_knowledge_acquisition.json"),"content_craft":read(LIVE/"nic_content_craft_9.json"),"forecast_profitability":read(INTEL/"nic_forecast_profitability.json")}
    result=build_contract(artifacts,read(MEMORY))
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    MEMORY.write_text(json.dumps({"updated_at":result["generated_at"],"known_gaps":result["known_gaps"],"last_contract_sha256":result["contract_sha256"]},indent=2)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"status":result["status"],"domain_count":len(result["domains"]),"input_status":{k:v["status"] for k,v in result["inputs"].items()},"known_gaps":result["known_gaps"],"previous_run_known_gaps":result["previous_run_known_gaps"],"trade_authorized":False,"publication_authorized":False},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"domains":len(result["domains"]),"known_gaps":result["known_gaps"],"trade_authorized":False,"publication_authorized":False},indent=2))
    return 0
if __name__=="__main__": raise SystemExit(main())
