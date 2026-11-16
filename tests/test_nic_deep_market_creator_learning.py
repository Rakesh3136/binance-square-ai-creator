import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("learning",ROOT/"src/nic_deep_market_creator_learning.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_covers_market_and_creator_domains():
    r=m.build_contract({k:{"status":"READY"} for k in ["market_intelligence","square_style","knowledge_acquisition","content_craft","forecast_profitability"]})
    names={x["domain"] for x in r["domains"]}
    assert {"market_structure","liquidity_microstructure","cross_asset_macro","forecast_science"} <= names
    assert {"creator_originality","reader_value","format_experimentation","visual_truth","audience_learning"} <= names
def test_learning_never_authorizes_trading_or_publication():
    r=m.build_contract({})
    assert r["guardrails"]["trade_authorized"] is False
    assert r["guardrails"]["publication_authorized"] is False
    assert r["guardrails"]["live_orders_enabled"] is False
    assert r["status"]=="LEARNING_WITH_GAPS"
def test_missing_evidence_is_recorded_and_prior_gaps_persist():
    r=m.build_contract({"market_intelligence":{"status":"READY"}},{"known_gaps":["old_source_gap"]})
    assert "old_source_gap" in r["known_gaps"]
    assert "forecast_profitability_artifact_missing" in r["known_gaps"]
