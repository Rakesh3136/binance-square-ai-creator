from pathlib import Path

workflow = Path(".github/workflows/nic-human-review-approval-validation.yml").read_text(encoding="utf-8")
autonomous = Path(".github/workflows/autonomous-market-creator.yml").read_text(encoding="utf-8")

def test_manual_resume_requires_explicit_human_approval():
    for required in (
        "workflow_dispatch:",
        "approved_for_publication:",
        "draft_sha256:",
        "human_thesis:",
        "original_insight:",
        "evidence_reviewed:",
        "author_attestation:",
        "nic-pending-human-review-",
        "nic_pending_human_review.py verify",
    ):
        assert required in workflow, f"missing required approval safety control: {required}"


def test_resume_revalidates_all_critical_gates_before_publisher():
    gates = [
        "nic21_2_hook_preflight.py",
        "nic21_originality_visual_truth.py",
        "nic_editorial_quality_gate.py",
        "elite_prepublication_gate.py",
        "content_integrity_gate_4.py",
        "nic22_3_publication_alignment_gate.py",
        "nic24_3_early_entry_gate.py",
        "nic24_2_evidence_content_integrity_gate.py",
        "production_manager.py",
    ]
    publisher = workflow.index("python src/binance_square_publisher.py")
    for gate in gates:
        assert workflow.index(gate) < publisher, f"{gate} must precede publisher"
    assert 'if: ${{ steps.resume_gates.outputs.publish == \'true\' }}' in workflow
    assert workflow.index("nic_pending_human_review.py verify", workflow.index("Publish the exact approved draft")) < publisher



def test_autonomous_flow_reviews_only_the_final_gated_draft():
    human_gate = autonomous.index("Final human creator contribution gate")
    chart_gate = autonomous.index("NIC 24.2 Evidence-to-Content Integrity")
    publisher = autonomous.index("python src/binance_square_publisher.py")
    assert human_gate > chart_gate
    assert autonomous.index("Preserve exact final draft and gate context for human review") > human_gate
    payload_section = autonomous[autonomous.index("Build final publication payload"):publisher]
    assert "steps.human_review.outputs.blocked != 'true'" in payload_section
    assert human_gate < publisher

def test_artifact_restores_repo_relative_data_paths_and_no_write_permission():
    assert "path: data" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "contents: write" not in workflow


if __name__ == "__main__":
    test_manual_resume_requires_explicit_human_approval()
    test_resume_revalidates_all_critical_gates_before_publisher()
    test_autonomous_flow_reviews_only_the_final_gated_draft()
    test_artifact_restores_repo_relative_data_paths_and_no_write_permission()
    print("NIC review resume workflow safety tests passed")
