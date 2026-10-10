import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "nic_forecast_laboratory", ROOT / "src" / "nic_forecast_laboratory.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_empty_prediction_queue_fails_closed():
    try:
        MODULE.require_forecast_evidence(0, 0, 0)
    except RuntimeError as exc:
        assert "zero candidates" in str(exc)
    else:
        raise AssertionError("an empty prediction queue must block the Forecast Laboratory")


def test_no_ready_candidates_fails_closed():
    try:
        MODULE.require_forecast_evidence(5, 0, 0)
    except RuntimeError as exc:
        assert "no candidate passed" in str(exc)
    else:
        raise AssertionError("failed market-data/hypothesis checks must block the Forecast Laboratory")


def test_no_fresh_snapshots_fails_closed():
    try:
        MODULE.require_forecast_evidence(5, 3, 0)
    except RuntimeError as exc:
        assert "no fresh immutable forecast snapshots" in str(exc)
    else:
        raise AssertionError("a cycle without fresh snapshots must not silently pass")


def test_fresh_forecast_evidence_is_allowed():
    MODULE.require_forecast_evidence(5, 3, 9)


if __name__ == "__main__":
    test_empty_prediction_queue_fails_closed()
    test_no_ready_candidates_fails_closed()
    test_no_fresh_snapshots_fails_closed()
    test_fresh_forecast_evidence_is_allowed()
    print("NIC Forecast Laboratory empty-evidence fail-closed tests: PASS")
