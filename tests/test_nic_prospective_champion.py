import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import nic_forecast_laboratory as lab

spec = importlib.util.spec_from_file_location("nic_prospective_champion", ROOT / "src/nic_prospective_champion.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def snapshot(fid, ts, *, side="BULLISH", decision="LONG_CANDIDATE", symbol="TST"):
    return {
        "forecast_id": fid,
        "timestamp": ts,
        "strategy_frozen_at": ts,
        "symbol": symbol,
        "side": side,
        "regime": "RANGE",
        "horizon_hours": 6,
        "decision": decision,
        "strategy_version": lab.STRATEGY_VERSION,
        "strategy_spec": lab.STRATEGY_SPEC,
        "strategy_spec_sha256": lab.STRATEGY_SPEC_SHA256,
        "validation_status": "PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN",
    }


def event(fid, ts, ret):
    resolved = datetime.fromisoformat(ts.replace("Z", "+00:00")) + timedelta(hours=7)
    return {"event_type": "FORECAST_RESOLVED", "forecast_id": fid,
            "resolved_at": resolved.isoformat(), "signed_return": ret}


def test_empty_evidence_stays_collecting_and_never_authorizes():
    report = m.evaluate([], [])
    assert report["status"] == "COLLECTING_PROSPECTIVE_OUTCOMES"
    assert report["trade_authorization"] is False
    assert report["publication_or_trade_authorization"] is False


def test_only_frozen_prospective_actionable_cohort_is_counted():
    ts = "2026-01-01T00:00:00+00:00"
    good = snapshot("good", ts, symbol="AAA")
    wait = snapshot("wait", ts, decision="WAIT", symbol="BBB")
    old = {"forecast_id": "old", "timestamp": ts, "symbol": "OLD",
           "side": "BULLISH", "horizon_hours": 6, "decision": "LONG_CANDIDATE"}
    report = m.evaluate([good, wait, old], [event("good", ts, 1.0), event("wait", ts, 1.0)])
    assert report["sample_counts"]["cohort_snapshot_count"] == 2
    assert report["sample_counts"]["cohort_resolved_actionable_count"] == 1
    assert report["sample_counts"]["cohort_excluded_non_actionable_count"] == 1
    assert report["trade_authorization"] is False


def test_outcome_cannot_resolve_before_forecast_horizon():
    ts = "2026-01-01T00:00:00+00:00"
    snap = snapshot("early", ts, symbol="AAA")
    early_event = {"event_type": "FORECAST_RESOLVED", "forecast_id": "early",
                   "resolved_at": "2026-01-01T03:00:00+00:00", "signed_return": 1.0}
    try:
        m.evaluate([snap], [early_event])
    except AssertionError as exc:
        assert "before its horizon matured" in str(exc)
    else:
        raise AssertionError("Premature outcome must fail closed")


def test_overlapping_same_symbol_forecasts_do_not_inflate_effective_sample():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    snaps, events = [], []
    for i, hour in enumerate((0, 1, 2, 6, 7, 12)):
        ts = (start + timedelta(hours=hour)).isoformat()
        fid = f"same-coin-{i}"
        snaps.append(snapshot(fid, ts, symbol="SAME"))
        events.append(event(fid, ts, 1.0))
    rows, _ = m.prospective_rows(snaps, events)
    effective, excluded = m.remove_overlapping_positions(rows)
    assert len(rows) == 6
    assert len(effective) == 3
    assert excluded == 3
    assert [r["timestamp"] for r in effective] == [
        (start + timedelta(hours=h)).isoformat() for h in (0, 6, 12)
    ]


def test_positive_but_weaker_than_opposite_direction_is_not_review_candidate():
    snaps, events = [], []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Small positive gross returns are eaten by execution costs, so this should
    # never be presented as evidence of a profitable champion.
    for i in range(40):
        ts = (start + timedelta(days=i)).isoformat()
        fid = f"weak-{i}"
        snaps.append(snapshot(fid, ts, symbol=f"WEAK{i}"))
        events.append(event(fid, ts, 0.05))
    report = m.evaluate(snaps, events, min_total=20, min_test=5)
    group = report["strategy_groups"]["BULLISH|6h"]
    assert group["status"] != "CANDIDATE_FOR_HUMAN_REVIEW_NOT_PROOF"
    assert group["matched_opposite_direction_baseline"]["beats_baseline_at_base_and_stress_costs"] is False
    assert report["trade_authorization"] is False


def test_positive_forward_cohort_is_review_candidate_not_proven():
    snaps, events = [], []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Independent symbols and daily spacing avoid same-symbol overlap. A small
    # negative tail ensures profit factor is finite and the cost-stress test matters.
    for i in range(40):
        ts = (start + timedelta(days=i)).isoformat()
        fid = f"cohort-{i}"
        snaps.append(snapshot(fid, ts, symbol=f"COIN{i}"))
        ret = -0.10 if i % 10 == 9 else 1.20
        events.append(event(fid, ts, ret))
    report = m.evaluate(snaps, events, min_total=20, min_test=5)
    assert report["status"] == "CANDIDATE_FOR_HUMAN_REVIEW_NOT_PROOF"
    group = report["strategy_groups"]["BULLISH|6h"]
    assert group["status"] == "CANDIDATE_FOR_HUMAN_REVIEW_NOT_PROOF"
    assert group["execution_cost_stress_test"]["passed"] is True
    baseline = group["matched_opposite_direction_baseline"]
    assert baseline["is_market_benchmark"] is False
    assert baseline["beats_baseline_at_base_and_stress_costs"] is True
    assert baseline["held_out_net_pnl_advantage"] > 0
    assert baseline["stress_net_pnl_advantage"] > 0
    assert group["promotion_allowed"] is False
    assert report["trade_authorization"] is False


if __name__ == "__main__":
    test_empty_evidence_stays_collecting_and_never_authorizes()
    test_only_frozen_prospective_actionable_cohort_is_counted()
    test_outcome_cannot_resolve_before_forecast_horizon()
    test_overlapping_same_symbol_forecasts_do_not_inflate_effective_sample()
    test_positive_but_weaker_than_opposite_direction_is_not_review_candidate()
    test_positive_forward_cohort_is_review_candidate_not_proven()
    print("NIC prospective champion tests: PASS")
