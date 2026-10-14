import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evidence_integrity", ROOT / "src/nic_evidence_outcome_integrity.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def fixture():
    snapshots = [
        {
            "forecast_id": "f-1",
            "timestamp": "2026-10-01T10:00:00+00:00",
            "symbol": "BTCUSDT",
            "side": "BULLISH",
            "decision": "LONG_CANDIDATE",
            "horizon_hours": 6,
            "source_provenance": {"provider":"Binance Spot Market Data API","endpoint":"https://data-api.binance.vision/api/v3/klines","instrument":"BTCUSDT","interval":"1h","closed_candle_open_time":"2026-10-01T09:00:00Z","closed_candle_as_of":"2026-10-01T10:00:00Z","retrieved_at":"2026-10-01T10:00:01Z","strategy_spec_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        },
        {
            "forecast_id": "f-2",
            "timestamp": "2026-10-01T11:00:00+00:00",
            "symbol": "ETHUSDT",
            "side": "BEARISH",
            "decision": "WAIT",
            "horizon_hours": 12,
            "source_provenance": {**{"provider":"Binance Spot Market Data API","endpoint":"https://data-api.binance.vision/api/v3/klines","instrument":"BTCUSDT","interval":"1h","closed_candle_open_time":"2026-10-01T09:00:00Z","closed_candle_as_of":"2026-10-01T10:00:00Z","retrieved_at":"2026-10-01T10:00:01Z","strategy_spec_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}, "instrument": "ETHUSDT"},
        },
    ]
    outcomes = [
        {"event_type": "FORECAST_RESOLVED", "forecast_id": "f-1", "signed_return": 1.2,
         "resolved_at": "2026-10-01T16:00:00+00:00"},
        {"event_type": "FORECAST_RESOLVED", "forecast_id": "f-2", "signed_return": -0.4,
         "resolved_at": "2026-10-01T23:00:00+00:00"},
    ]
    snapshot_hash, outcomes_hash = "snapshot-sha", "outcome-sha"
    report = {
        "status": "NOT_PROVEN",
        "resolved_forecast_count": 2,
        "sample_count": 1,
        "source_evidence": m.source_evidence(snapshots, outcomes, 2, snapshot_hash, outcomes_hash),
    }
    return snapshots, outcomes, report, snapshot_hash, outcomes_hash


def test_valid_ledgers_verify_integrity_not_profitability():
    result = m.evaluate_evidence(*fixture())
    assert result["status"] == "VERIFIED"
    assert result["joined_resolved_forecast_count"] == 2
    assert result["joined_actionable_sample_count"] == 1
    assert result["profitability_proven"] is False
    assert result["trade_authorized"] is False
    assert result["publication_authorized"] is False


def test_empty_ledgers_are_blocked_not_profitable():
    snapshots, outcomes = [], []
    snapshot_hash = outcomes_hash = "empty-ledger-sha"
    report = {
        "status": "NOT_PROVEN",
        "resolved_forecast_count": 0,
        "sample_count": 0,
        "source_evidence": m.source_evidence(snapshots, outcomes, 0, snapshot_hash, outcomes_hash),
    }
    result = m.evaluate_evidence(snapshots, outcomes, report, snapshot_hash, outcomes_hash)
    assert result["status"] == "BLOCKED"
    assert result["joined_resolved_forecast_count"] == 0
    assert result["profitability_proven"] is False


def test_snapshot_without_terminal_outcome_is_not_counted_as_resolved():
    snapshots, outcomes, report, sh, oh = fixture()
    outcomes = outcomes[:1]
    report["source_evidence"] = m.source_evidence(snapshots, outcomes, 1, sh, oh)
    report["resolved_forecast_count"], report["sample_count"] = 1, 1
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "VERIFIED"
    assert result["joined_resolved_forecast_count"] == 1


def test_orphan_outcome_fails_closed():
    snapshots, outcomes, report, sh, oh = fixture()
    outcomes[0]["forecast_id"] = "missing-snapshot"
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "FAILED"
    assert any("orphan_terminal_outcome" in error for error in result["errors"])


def test_duplicate_snapshot_id_fails_closed():
    snapshots, outcomes, report, sh, oh = fixture()
    snapshots.append(dict(snapshots[0]))
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "FAILED"
    assert any("duplicate_snapshot_forecast_id" in error for error in result["errors"])


def test_report_counts_cannot_disagree_with_joined_ledger():
    snapshots, outcomes, report, sh, oh = fixture()
    report["resolved_forecast_count"] = 6210
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "FAILED"
    assert any("report_resolved_forecast_count_mismatch" in error for error in result["errors"])


def test_missing_provenance_blocks_verification():
    snapshots, outcomes, report, sh, oh = fixture()
    snapshots[0].pop("source_provenance")
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "BLOCKED"
    assert any("snapshot_missing_source_provenance:f-1" in warning for warning in result["warnings"])


def test_source_hash_mismatch_fails_closed():
    snapshots, outcomes, report, sh, oh = fixture()
    result = m.evaluate_evidence(snapshots, outcomes, report, "changed-hash", oh)
    assert result["status"] == "FAILED"
    assert any("snapshot_ledger_sha256" in error for error in result["errors"])


def test_malformed_jsonl_is_rejected(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"forecast_id":"ok"}\nnot-json\n', encoding="utf-8")
    try:
        m.read_jsonl(path)
    except m.EvidenceError:
        return
    raise AssertionError("malformed evidence JSONL must be rejected")


def test_actionable_sample_requires_canonical_source_provenance():
    snapshots, outcomes, report, sh, oh = fixture()
    snapshots[0]["source_provenance"] = {"url": "https://example.com/only-a-url"}
    report["sample_count"] = 0
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "BLOCKED"
    assert result["joined_resolved_forecast_count"] == 2
    assert result["joined_actionable_sample_count"] == 0


def test_legacy_url_does_not_count_as_source_provenance():
    snapshots, outcomes, report, sh, oh = fixture()
    snapshots[1].pop("source_provenance")
    snapshots[1]["source_url"] = "https://example.com/eth"
    result = m.evaluate_evidence(snapshots, outcomes, report, sh, oh)
    assert result["status"] == "BLOCKED"
    assert result["joined_actionable_sample_count"] == 1
