import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("distill", ROOT / "src/nic_distillation_lab.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def example(eid="a", date="2026-10-01T00:00:00Z", group="g1", **extra):
    row = {
        "example_id": eid,
        "task_type": "market_analysis",
        "input": "At decision time, assess the evidence and uncertainty.",
        "teacher_target": "State evidence, uncertainty, invalidation and wait if evidence is weak.",
        "label": "REVISE",
        "created_at": date,
        "review_status": "VERIFIED",
        "evidence_refs": [{
            "url": "https://example.com/source",
            "sha256": "abc123",
            "observed_at": "2026-10-01T00:00:00Z",
        }],
        "source_group": group,
    }
    row.update(extra)
    return row


def test_grounded_examples_split_by_source_group():
    result = m.build_dataset([
        example("a", "2026-10-01T00:00:00Z", "old-source"),
        example("b", "2026-10-02T00:00:00Z", "new-source"),
    ])
    assert result["summary"]["accepted"] == 2
    assert result["summary"]["train"] == 1
    assert result["summary"]["evaluation"] == 1
    assert result["summary"]["split_group_overlap"] is False


def test_unverified_or_unhashed_examples_are_rejected():
    row = example("a")
    row["review_status"] = "PENDING"
    row["evidence_refs"] = [{"url": "https://example.com"}]
    result = m.build_dataset([row])
    assert result["summary"]["accepted"] == 0
    assert any("not_reviewed_or_verified" in x["reasons"] for x in result["rejected"])
    assert any("missing_timestamped_hashed_evidence" in x["reasons"] for x in result["rejected"])


def test_forecast_outcomes_require_terminal_evidence_and_no_label_leakage():
    base = example("f1", task_type="forecast_outcome", forecast_id="f-1",
                   outcome_status="UNRESOLVED")
    result = m.build_dataset([base])
    assert result["summary"]["accepted"] == 0
    assert "forecast_outcome_not_terminal_verified" in result["rejected"][0]["reasons"]
    base["outcome_status"] = "TERMINAL_VERIFIED"
    base["input"] = "Terminal label: WIN. This is leaked future data."
    result = m.build_dataset([base])
    assert "outcome_leakage_in_input" in result["rejected"][0]["reasons"]


def test_rewards_need_verified_reward_and_canonical_post():
    row = example("p1", task_type="creator_reward", reward_status="PENDING",
                  canonical_post_id="post-1")
    result = m.build_dataset([row])
    assert "creator_reward_not_verified" in result["rejected"][0]["reasons"]


def test_duplicate_ids_are_rejected_and_gates_never_change():
    result = m.build_dataset([example("same", group="a"), example("same", group="b")])
    assert result["summary"]["accepted"] == 1
    assert "duplicate_example_id" in result["rejected"][0]["reasons"]
    assert result["guardrails"]["trade_authorized"] is False
    assert result["guardrails"]["publication_authorized"] is False
    assert result["guardrails"]["fine_tuning_performed"] is False


def test_too_few_examples_cannot_be_promoted():
    result = m.build_dataset([example("only", group="one")])
    assert result["status"] == "BLOCKED_INSUFFICIENT_VERIFIED_DATA"
    assert result["promotion_policy"]["insufficient_data_action"] == "DO_NOT_TRAIN_OR_PROMOTE"
