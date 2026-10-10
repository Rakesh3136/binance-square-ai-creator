import hashlib
import sys
from pathlib import Path

sys.path.insert(0, "src")
import nic_human_creator_contribution_gate as gate


def valid_input(post):
    return {
        "draft_sha256": hashlib.sha256(post.encode("utf-8")).hexdigest(),
        "human_thesis": "My independent thesis explains why this market setup matters.",
        "original_insight": "The useful detail is the divergence between price and participation.",
        "evidence_reviewed": "I reviewed the current chart and the cited source before approving.",
        "approved_for_publication": True,
        "author_attestation": "I reviewed the evidence and authored the editorial contribution",
    }


def test_valid_human_review_passes():
    post = "$ABC is consolidating while participation fades."
    result = gate.evaluate(post, valid_input(post))
    assert result["publish"] is True
    assert result["failures"] == []


def test_missing_human_input_blocks():
    result = gate.evaluate("$ABC is moving.", {})
    assert result["publish"] is False
    assert "explicit_human_approval_missing" in result["failures"]


def test_stale_review_hash_blocks():
    post = "$ABC is consolidating while participation fades."
    data = valid_input(post)
    data["draft_sha256"] = hashlib.sha256(b"older draft").hexdigest()
    result = gate.evaluate(post, data)
    assert "human_review_does_not_match_current_draft" in result["failures"]
    assert result["publish"] is False


def test_short_generic_contribution_blocks():
    post = "$ABC is consolidating while participation fades."
    data = valid_input(post)
    data["original_insight"] = "Interesting."
    result = gate.evaluate(post, data)
    assert "original_insight_missing_or_too_short" in result["failures"]


def test_missing_attestation_blocks():
    post = "$ABC is consolidating while participation fades."
    data = valid_input(post)
    data["author_attestation"] = "looks good"
    result = gate.evaluate(post, data)
    assert "author_attestation_missing" in result["failures"]


if __name__ == "__main__":
    test_valid_human_review_passes()
    test_missing_human_input_blocks()
    test_stale_review_hash_blocks()
    test_short_generic_contribution_blocks()
    test_missing_attestation_blocks()
    print("NIC human creator contribution tests passed")
