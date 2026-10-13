import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("learning",ROOT/"src/nic_deep_market_creator_learning.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_covers_market_and_creator_domains():
    r=m.build_contract({k:{"status":"READY"} for k in m.REQUIRED_INPUTS})
    names={x["domain"] for x in r["domains"]}
    assert {"market_structure","liquidity_microstructure","cross_asset_macro","forecast_science"} <= names
    assert {"creator_originality","reader_value","format_experimentation","visual_truth","audience_learning"} <= names
    assert r["status"]=="LEARNING_INPUTS_PRESENT"

def test_learning_never_authorizes_trading_or_publication():
    r=m.build_contract({})
    assert r["guardrails"]["trade_authorized"] is False
    assert r["guardrails"]["publication_authorized"] is False
    assert r["guardrails"]["live_orders_enabled"] is False
    assert r["status"]=="LEARNING_WITH_GAPS"

def test_missing_evidence_is_recorded_and_prior_gaps_do_not_stay_active_forever():
    r=m.build_contract({"market_intelligence":{"status":"READY"}},{"known_gaps":["old_source_gap"]})
    assert "old_source_gap" in r["previous_run_known_gaps"]
    assert "old_source_gap" not in r["known_gaps"]
    assert "forecast_profitability_artifact_missing" in r["known_gaps"]

def test_explicit_failed_or_stale_artifact_is_not_counted_as_present():
    artifacts={k:{"status":"READY","records":[1]} for k in m.REQUIRED_INPUTS}
    artifacts["forecast_profitability"]={"status":"FAILED","records":[1]}
    r=m.build_contract(artifacts)
    assert r["status"]=="LEARNING_WITH_GAPS"
    assert "forecast_profitability_artifact_status_failed" in r["known_gaps"]
    assert r["inputs"]["forecast_profitability"]["status"]=="FAILED"

def test_empty_artifact_is_missing_even_if_key_exists():
    artifacts={k:{"status":"READY","records":[1]} for k in m.REQUIRED_INPUTS}
    artifacts["square_style"]={}
    r=m.build_contract(artifacts)
    assert "square_style_artifact_missing" in r["known_gaps"]

def test_unrecognized_status_fails_closed():
    artifacts={k:{"status":"READY","records":[1]} for k in m.REQUIRED_INPUTS}
    artifacts["knowledge_acquisition"]={"status":"STALE","records":[1]}
    r=m.build_contract(artifacts)
    assert "knowledge_acquisition_artifact_status_stale" in r["known_gaps"]
