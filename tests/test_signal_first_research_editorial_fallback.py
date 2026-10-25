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


if __name__ == "__main__":
    test_fresh_qualified_research_becomes_editorial_only_candidate()
    test_stale_research_cannot_create_candidate()
    test_weak_evidence_or_missing_epistemic_note_is_excluded()
    test_non_live_asset_is_excluded()
    print("Signal-First research editorial fallback tests passed")
