from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nic_prediction_contract_validator import evidence_tier, wilson_lower_90


def test_wilson_bound_is_below_point_estimate():
    lower = wilson_lower_90(65, 100)
    assert lower is not None
    assert 0.65 > lower > 0.5


def test_small_sample_is_not_experience():
    assert evidence_tier(10, 0.9, wilson_lower_90(9, 10)) == "INSUFFICIENT_DATA"


def test_strong_evidence_requires_both_sample_and_rate():
    lower = wilson_lower_90(70, 100)
    assert evidence_tier(100, 0.70, lower) == "STRONG_EVIDENCE"


def test_weak_edge_is_not_publishable_evidence():
    lower = wilson_lower_90(55, 100)
    assert evidence_tier(100, 0.55, lower) == "WEAK_OR_UNPROVEN"


if __name__ == "__main__":
    test_wilson_bound_is_below_point_estimate()
    test_small_sample_is_not_experience()
    test_strong_evidence_requires_both_sample_and_rate()
    test_weak_edge_is_not_publishable_evidence()
    print("NIC 23 trade evidence tests passed")
