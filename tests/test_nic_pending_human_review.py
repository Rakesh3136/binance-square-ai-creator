import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
import nic_pending_human_review as pending


def write_draft(path, text="$ABC is consolidating while participation fades."):
    path.write_text(json.dumps({"draft": {"text": text, "symbol": "ABC"}}), encoding="utf-8")


def valid_input(post):
    return {
        "draft_sha256": pending.sha256_text(post),
        "human_thesis": "My independent thesis explains why this market setup matters.",
        "original_insight": "The useful detail is divergence between price and participation.",
        "evidence_reviewed": "I reviewed the current chart and source before approving.",
        "approved_for_publication": True,
        "author_attestation": "I reviewed the evidence and authored the editorial contribution",
    }


def test_pending_package_binds_exact_file_and_text():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "draft.json"
        write_draft(path)
        package = pending.prepare(path, Path(tmp) / "pending.json")
        assert package["status"] == "PENDING_HUMAN_REVIEW"
        assert package["policy"]["publication_authorized"] is False
        assert pending.verify_approval(package, valid_input(package["draft_text"]), path) == []


def test_changed_draft_invalidates_approval():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "draft.json"
        write_draft(path)
        package = pending.prepare(path, Path(tmp) / "pending.json")
        human = valid_input(package["draft_text"])
        write_draft(path, "$ABC has already broken out.")
        failures = pending.verify_approval(package, human, path)
        assert "pending_draft_text_changed_or_missing" in failures
        assert "pending_draft_file_changed_or_missing" in failures


def test_missing_human_approval_blocks():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "draft.json"
        write_draft(path)
        package = pending.prepare(path)
        human = valid_input(package["draft_text"])
        human["approved_for_publication"] = False
        assert "explicit_approval_missing" in pending.verify_approval(package, human, path)


if __name__ == "__main__":
    test_pending_package_binds_exact_file_and_text()
    test_changed_draft_invalidates_approval()
    test_missing_human_approval_blocks()
    print("NIC pending human review tests passed")
