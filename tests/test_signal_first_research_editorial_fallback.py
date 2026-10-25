import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("signal_first_router", ROOT / "src" / "signal_first_router.py")
router = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(router)


def artifact(generated_at, rows):
    return {"generated_at": generated_at, "potential_gems": rows, "potential_risks": []}


def row(**overrides):
    base = {
        "symbol": "FOR",
        "information_advantage_score": 78,
        "undercoverage_score": 70,
        "evidence_score": 61,
        "epistemic_note": "Screening signal, not certainty.",
        "missing_evidence": ["market_cap"],
    }
    return {**base, **overrides}


def test_fresh_qualified_research_becomes_editorial_only_candidate():
    now = datetime.now(timezone.utc)
    result = router.research_editorial_candidates(
        artifact(now.isoformat(), [row()]), {"FOR", "BTC"}, now=now
    )
    assert len(result) == 1
    candidate = result[0]
    assert candidate["category"] == "research_insight"
    assert candidate["editorial_only"] is True
    assert candidate["symbol"] == "FOR"
    assert candidate["score"] == 78


def test_stale_research_cannot_create_candidate():
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(minutes=46)).isoformat()
    assert router.research_editorial_candidates(
        artifact(stale, [row()]), {"FOR"}, now=now
    ) == []


def test_weak_evidence_or_missing_epistemic_note_is_excluded():
    now = datetime.now(timezone.utc)
    research = artifact(now.isoformat(), [
        row(evidence_score=49),
        row(symbol="DATA", epistemic_note=""),
        row(symbol="QNT", information_advantage_score=71),
    ])
    assert router.research_editorial_candidates(research, {"FOR", "DATA", "QNT"}, now=now) == []


def test_non_live_asset_is_excluded():
    now = datetime.now(timezone.utc)
    assert router.research_editorial_candidates(
        artifact(now.isoformat(), [row()]), {"BTC"}, now=now
    ) == []



def test_rejected_editorial_candidate_is_not_misrouted_as_trade():
    candidate = {
        "symbol": "FOR",
        "category": "research_insight",
        "lane": "research_insight",
        "score": 60,
        "editorial_only": True,
        "research": {
            "evidence_score": 49,
            "information_advantage_score": 60,
            "undercoverage_score": 70,
            "epistemic_note": "Screening signal, not certainty.",
        },
    }
    router.content_plan_for = lambda _x: {}
    router.prediction_quality_for = lambda _x: {}
    router.forecast_evidence_for = lambda x: x
    router.timing_for = lambda *_args: {"allowed": True, "timing_state": "WATCH"}
    router.blocked = lambda *_args: None
    router.derive = lambda *_args: (_ for _ in ()).throw(AssertionError("editorial candidate must not enter trade derivation"))
    selected, blocked = router.choose(
        [candidate], [], {}, {}, {"FOR"}, allow_editorial=True
    )
    assert selected is None
    assert any(row.get("reason") == "editorial_candidate_failed_evidence_requirements" for row in blocked)
    assert any(row.get("category") == "research_insight" for row in blocked)


def test_rejection_diagnostics_explain_why_no_research_candidate_qualified():
    now = datetime.now(timezone.utc)
    research = artifact(now.isoformat(), [
        row(symbol="FOR", information_advantage_score=60, undercoverage_score=40, evidence_score=20),
        row(symbol="DATA", epistemic_note=""),
        row(symbol="DELISTED"),
    ])
    candidates, diagnostics = router.analyze_research_editorial_candidates(
        research, {"FOR", "DATA", "BTC"}, now=now
    )
    assert candidates == []
    assert diagnostics["artifact_fresh"] is True
    assert diagnostics["input_rows"] == 3
    assert diagnostics["qualified_rows"] == 0
    assert diagnostics["rejected_rows"] == 3
    assert diagnostics["artifact_rejection_reason"] == "no_candidate_cleared_research_editorial_thresholds"
    assert diagnostics["rejection_reason_counts"]["information_advantage_below_minimum"] == 1
    assert diagnostics["rejection_reason_counts"]["undercoverage_below_60"] == 1
    assert diagnostics["rejection_reason_counts"]["evidence_below_50"] == 1
    assert diagnostics["rejection_reason_counts"]["missing_epistemic_note"] == 1
    assert diagnostics["rejection_reason_counts"]["asset_not_in_live_binance_usdt_universe"] == 1


def test_diagnostics_identify_stale_research_artifact():
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(minutes=46)).isoformat()
    candidates, diagnostics = router.analyze_research_editorial_candidates(
        artifact(stale, [row()]), {"FOR"}, now=now
    )
    assert candidates == []
    assert diagnostics["artifact_fresh"] is False
    assert diagnostics["artifact_rejection_reason"] == "research_artifact_stale_or_future_dated"


if __name__ == "__main__":
    test_fresh_qualified_research_becomes_editorial_only_candidate()
    test_stale_research_cannot_create_candidate()
    test_weak_evidence_or_missing_epistemic_note_is_excluded()
    test_non_live_asset_is_excluded()
    test_rejected_editorial_candidate_is_not_misrouted_as_trade()
    test_rejection_diagnostics_explain_why_no_research_candidate_qualified()
    test_diagnostics_identify_stale_research_artifact()
    print("Signal-First research editorial fallback tests passed")
