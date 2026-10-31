import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nic_native_writer", ROOT / "src" / "nic_native_writer.py")
writer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(writer)


def test_exhausted_research_writer_emits_evidence_gap_not_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(writer, "RECENT_LOG", tmp_path / "publication_log.jsonl")
    context = {
        "preflight": {
            "selected_opportunity": {
                "symbol": "HOT",
                "category": "research_insight",
                "trade_setup": {},
            }
        },
        "publication": {
            "symbol": "HOT",
            "category": "research_insight",
            "content_lane": "research_insight",
            "timing_state": "EXHAUSTED",
            "research_observation": {
                "news_count": 0,
                "official_evidence_count": 0,
                "missing_evidence": [
                    "market_cap", "fdv", "circulating_supply",
                    "product_adoption", "revenue_or_fees",
                    "holder_concentration", "unlocks",
                    "security_audits", "external_news_corroboration",
                ],
            },
        },
        "market": {
            "top_gainers": [{
                "symbol": "HOTUSDT",
                "last_price": 0.000357,
                "price_change_percent": 13.333,
                "quote_volume_usdt": 2383064.31,
                "intraday_range_percent": 40.056,
            }]
        },
    }
    result = writer.build(context)
    post = result["draft"]["post"]
    assert result["draft"]["content_category"] == "research_insight"
    assert "Timing is exhausted for a fresh entry" in post
    assert "No independent news corroboration is recorded" in post
    assert "13.3%" in post
    assert "$HOT" in post
    assert post.count("?") == 1
    assert 280 <= len(post) <= 700
    assert "entry:" not in post.lower()
    assert "stop-loss:" not in post.lower()
