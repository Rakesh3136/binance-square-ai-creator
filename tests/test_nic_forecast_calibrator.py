import importlib.util
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("calibrator", ROOT / "src/nic_forecast_calibrator.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_small_samples_are_shrunk():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    snapshot = {
        "forecast_id": "A", "validation_status": "PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN",
        "horizon_hours": 6, "side": "BULLISH", "regime": "RANGE", "forecast_probability": 0.8,
        "source_provenance": {
            "provider": "Binance Spot Market Data API",
            "endpoint": "https://data-api.binance.vision/api/v3/klines",
            "instrument": "BTCUSDT", "interval": "1h",
            "closed_candle_open_time": "2026-10-01T09:00:00Z",
            "closed_candle_as_of": "2026-10-01T10:00:00Z",
            "retrieved_at": "2026-10-01T10:00:01Z",
            "strategy_spec_sha256": "a" * 64,
        },
    }
    event = {"event_type": "FORECAST_RESOLVED", "forecast_id": "A", "signed_return": 10, "hit": True}
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text(json.dumps(snapshot) + chr(10))
        events.write_text(json.dumps(event) + chr(10))
        cell = m.calibrate()["BULLISH|RANGE|6h"]
        assert cell["calibrated_probability"] < 0.8
        assert cell["trusted"] is False
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events

def test_probability_metrics_are_computed():
    metrics = m.metrics([{"forecast_probability":0.8,"hit":True},{"forecast_probability":0.2,"hit":False}])
    assert metrics["samples"] == 2
    assert metrics["brier_score"] == 0.04
    assert metrics["log_loss"] > 0


def test_new_terminal_events_join_immutable_snapshots():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    snapshot = {"forecast_id":"A","timestamp":"2026-10-01T00:00:00+00:00","horizon_hours":6,
                "side":"BULLISH","regime":"RANGE","forecast_probability":0.8,"resolved":False,
                "validation_status":"PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN",
                "source_provenance":{"provider":"Binance Spot Market Data API","endpoint":"https://data-api.binance.vision/api/v3/klines",
                "instrument":"BTCUSDT","interval":"1h","closed_candle_open_time":"2026-10-01T09:00:00Z",
                "closed_candle_as_of":"2026-10-01T10:00:00Z","retrieved_at":"2026-10-01T10:00:01Z",
                "strategy_spec_sha256":"a"*64}}
    event = {"event_type":"FORECAST_RESOLVED","event_id":"A|resolved","forecast_id":"A",
             "signed_return":1.25,"hit":True}
    unresolved = {"forecast_id":"B","horizon_hours":6,"side":"BULLISH","regime":"RANGE",
                  "forecast_probability":0.9,"resolved":False,"validation_status":"PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN",
                  "source_provenance":snapshot["source_provenance"]}
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text("\n".join(json.dumps(x) for x in [snapshot, unresolved]) + "\n")
        events.write_text(json.dumps(event) + "\n")
        rows = m.read()
        assert len(rows) == 1 and rows[0]["forecast_id"] == "A"
        assert rows[0]["hit"] is True and rows[0]["signed_return"] == 1.25
        assert snapshot["resolved"] is False
        assert m.metrics(rows)["samples"] == 1
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events


def test_missing_or_unresolved_outcomes_are_not_scored():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    events = ROOT / "tests" / "tmp_forecast_events.jsonl"
    old_ledger, old_events = m.LEDGER, m.EVENTS
    try:
        m.LEDGER, m.EVENTS = ledger, events
        ledger.write_text('{"forecast_id":"B","horizon_hours":24,"forecast_probability":0.99,"resolved":false}\n')
        events.write_text("")
        assert m.read() == []
        assert m.metrics(m.read())["samples"] == 0
    finally:
        ledger.unlink(missing_ok=True); events.unlink(missing_ok=True)
        m.LEDGER, m.EVENTS = old_ledger, old_events



def test_artifact_integrity_accepts_consistent_ledgers_and_reports():
    snapshots = [{"forecast_id":"A","horizon_hours":6,"forecast_probability":0.8,"resolved":False},
                 {"forecast_id":"B","horizon_hours":24,"forecast_probability":0.6,"resolved":False}]
    events = [{"event_type":"FORECAST_RESOLVED","forecast_id":"A","signed_return":1,"hit":True}]
    calibration = {"global_metrics":{"samples":1},"resolved_event_samples":1}
    matrix = {"resolved_event_count":1}
    result = m.validate_artifact_integrity(snapshots, events, calibration, matrix)
    assert result["calibration_samples"] == 1
    assert result["terminal_events"] == 1


def test_artifact_integrity_rejects_orphan_terminal_event():
    try:
        m.validate_artifact_integrity([], [{"event_type":"FORECAST_RESOLVED","forecast_id":"ORPHAN"}],
                                      {"global_metrics":{"samples":0}}, {"resolved_event_count":1})
    except AssertionError as exc:
        assert "lack forecast snapshots" in str(exc)
    else:
        raise AssertionError("orphan outcome must fail integrity validation")


def test_artifact_integrity_rejects_stale_calibration_count():
    snapshots = [{"forecast_id":"A","horizon_hours":6,"forecast_probability":0.8,"resolved":False}]
    events = [{"event_type":"FORECAST_RESOLVED","forecast_id":"A","signed_return":1,"hit":True}]
    try:
        m.validate_artifact_integrity(snapshots, events,
                                      {"global_metrics":{"samples":720},"resolved_event_samples":720},
                                      {"resolved_event_count":1})
    except AssertionError as exc:
        assert "Calibration sample mismatch" in str(exc)
    else:
        raise AssertionError("stale calibration report must fail integrity validation")


def test_artifact_integrity_rejects_matrix_event_count_mismatch():
    snapshots = [{"forecast_id":"A","horizon_hours":6,"forecast_probability":0.8,"resolved":False}]
    events = [{"event_type":"FORECAST_RESOLVED","forecast_id":"A","signed_return":1,"hit":True}]
    try:
        m.validate_artifact_integrity(snapshots, events,
                                      {"global_metrics":{"samples":1},"resolved_event_samples":1},
                                      {"resolved_event_count":3480})
    except AssertionError as exc:
        assert "Signal matrix event mismatch" in str(exc)
    else:
        raise AssertionError("stale matrix count must fail integrity validation")



def test_artifact_integrity_rejects_duplicate_snapshot_ids():
    snapshots = [{"forecast_id": "A", "horizon_hours": 6, "forecast_probability": 0.8, "resolved": False},
                 {"forecast_id": "A", "horizon_hours": 6, "forecast_probability": 0.8, "resolved": False}]
    try:
        m.validate_artifact_integrity(snapshots, [], {"global_metrics": {"samples": 0}},
                                      {"resolved_event_count": 0})
    except AssertionError as exc:
        assert "Duplicate immutable forecast snapshot IDs" in str(exc)
    else:
        raise AssertionError("duplicate immutable snapshots must fail integrity validation")


def test_artifact_integrity_rejects_conflicting_hit_label():
    snapshots = [{"forecast_id": "A", "horizon_hours": 6, "forecast_probability": 0.8, "resolved": False}]
    events = [{"event_type": "FORECAST_RESOLVED", "forecast_id": "A", "signed_return": 1.0, "hit": False}]
    try:
        m.validate_artifact_integrity(snapshots, events,
                                      {"global_metrics": {"samples": 1}, "resolved_event_samples": 1},
                                      {"resolved_event_count": 1})
    except AssertionError as exc:
        assert "conflicts with signed_return" in str(exc)
    else:
        raise AssertionError("conflicting outcome labels must fail integrity validation")


def test_artifact_integrity_rejects_invalid_probability():
    snapshots = [{"forecast_id": "A", "horizon_hours": 6, "forecast_probability": 1.5, "resolved": False}]
    events = [{"event_type": "FORECAST_RESOLVED", "forecast_id": "A", "signed_return": 1.0, "hit": True}]
    try:
        m.validate_artifact_integrity(snapshots, events,
                                      {"global_metrics": {"samples": 1}, "resolved_event_samples": 1},
                                      {"resolved_event_count": 1})
    except AssertionError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("out-of-range probabilities must fail integrity validation")


def test_malformed_jsonl_fails_closed():
    ledger = ROOT / "tests" / "tmp_forecast_ledger.jsonl"
    old_ledger = m.LEDGER
    try:
        m.LEDGER = ledger
        ledger.write_text('{"forecast_id":"A"}\n{broken json}\n')
        try:
            m.load_jsonl(ledger)
        except AssertionError as exc:
            assert "Invalid forecast ledger row" in str(exc)
        else:
            raise AssertionError("malformed source evidence must not be silently ignored")
    finally:
        ledger.unlink(missing_ok=True)
        m.LEDGER = old_ledger


def test_failed_integrity_does_not_overwrite_last_calibration_report():
    import tempfile
    old_root, old_ledger, old_events, old_out = m.ROOT, m.LEDGER, m.EVENTS, m.OUT
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intelligence = root / "data" / "intelligence"
            intelligence.mkdir(parents=True)
            m.ROOT = root
            m.LEDGER = intelligence / "nic_forecast_prospective_cohort.jsonl"
            m.EVENTS = intelligence / "nic_forecast_prospective_outcome_events.jsonl"
            m.OUT = intelligence / "nic_forecast_calibration.json"
            m.LEDGER.write_text("")
            m.EVENTS.write_text(json.dumps({"event_type":"FORECAST_RESOLVED","forecast_id":"ORPHAN","signed_return":1}) + "\n")
            m.OUT.write_text('{"last_known_good":true}')
            try:
                m.main()
            except AssertionError as exc:
                assert "lack forecast snapshots" in str(exc)
            else:
                raise AssertionError("orphan terminal event must fail calibration")
            assert json.loads(m.OUT.read_text()) == {"last_known_good": True}
    finally:
        m.ROOT, m.LEDGER, m.EVENTS, m.OUT = old_root, old_ledger, old_events, old_out




def test_production_workflow_runs_forecast_lab_resolver_calibrator_in_order():
    workflow = (ROOT / ".github" / "workflows" / "autonomous-market-creator.yml").read_text()
    lab_workflow = (ROOT / ".github" / "workflows" / "nic-forecast-laboratory.yml").read_text()
    feedback_workflow = (ROOT / ".github" / "workflows" / "creator-8-3-feedback.yml").read_text()
    shared_lock = "nic-forecast-production-evidence-${{ github.ref }}"
    assert shared_lock in workflow
    assert shared_lock in lab_workflow
    assert "cancel-in-progress: false" in workflow
    assert "cancel-in-progress: false" in lab_workflow
    assert shared_lock in feedback_workflow
    assert "cancel-in-progress: false" in feedback_workflow
    lab = workflow.index("run_component nic_forecast_laboratory python src/nic_forecast_laboratory.py")
    resolver = workflow.index("run_component nic_forecast_outcome_resolver python src/nic_forecast_outcome_resolver.py")
    calibrator = workflow.index("run_component nic_forecast_calibrator python src/nic_forecast_calibrator.py")
    profitability = workflow.index("run_component nic_forecast_profitability python src/nic_forecast_profitability.py")
    validator = workflow.index("run_component nic_prediction_contract_validator python src/nic_prediction_contract_validator.py")
    assert lab < resolver < calibrator < profitability < validator
    assert "data/intelligence/nic_forecast_profitability.json" in workflow
    assert "src/nic_forecast_profitability.py" in lab_workflow
    assert "tests/test_nic_forecast_profitability.py" in lab_workflow
    assert "FAILED nic_forecast_calibration_artifact_missing" in workflow
    assert "Persist Forecast Laboratory evidence ledgers" in workflow
    assert "git add -- data/intelligence/nic_forecast_truth_ledger.jsonl" in workflow
    assert "git stash push --include-untracked" in workflow
    assert "git fetch origin main" in workflow
    assert "git rebase origin/main" in workflow
    assert "NIC_EVIDENCE_COMMIT" in workflow
    assert "Merge and reconcile NIC Forecast Laboratory evidence" in workflow
    reconcile = (ROOT / "src" / "nic_forecast_evidence_reconcile.py").read_text()
    assert "lambda row: str(row.get(\"forecast_id\") or \"\")" in reconcile
    assert "python src/nic_forecast_evidence_reconcile.py" in workflow
    assert "python src/nic_forecast_outcome_resolver.py" in workflow
    assert "python src/nic_forecast_calibrator.py" in workflow
    fallback_calibrator = workflow.rindex("python src/nic_forecast_calibrator.py")
    fallback_profitability = workflow.index("python src/nic_forecast_profitability.py", fallback_calibrator)
    assert fallback_calibrator < fallback_profitability
    assert "source_evidence" in (ROOT / "src" / "nic_forecast_profitability.py").read_text()
    assert "net_mean_return_lower_bound_pct" in (ROOT / "src" / "nic_forecast_profitability.py").read_text()
    assert "for attempt in 1 2 3" in workflow
    assert "git push origin HEAD:main" in workflow
    assert "Forecast evidence persistence failed after three safe push attempts" in workflow
    assert "paths-ignore:" in workflow


if __name__ == "__main__":
    test_small_samples_are_shrunk()
    test_probability_metrics_are_computed()
    test_new_terminal_events_join_immutable_snapshots()
    test_missing_or_unresolved_outcomes_are_not_scored()
    test_artifact_integrity_accepts_consistent_ledgers_and_reports()
    test_artifact_integrity_rejects_orphan_terminal_event()
    test_artifact_integrity_rejects_stale_calibration_count()
    test_artifact_integrity_rejects_matrix_event_count_mismatch()
    test_artifact_integrity_rejects_duplicate_snapshot_ids()
    test_artifact_integrity_rejects_conflicting_hit_label()
    test_artifact_integrity_rejects_invalid_probability()
    test_malformed_jsonl_fails_closed()
    test_failed_integrity_does_not_overwrite_last_calibration_report()
    test_production_workflow_runs_forecast_lab_resolver_calibrator_in_order()
    print("NIC forecast event-ledger calibration tests: PASS")
