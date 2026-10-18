"""Provider-agnostic NIC assistant core.

This is an orchestration contract, not an LLM implementation. It plans work,
records auditable learning items, and keeps external actions behind explicit
approval. A model provider (NIC-native, Claude API, or another authorized API)
can be attached later through a separately tested adapter.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

ROLES = {
    "market_researcher": {"reads": ["public_market_data", "public_news", "official_project_sources"], "writes": ["research_brief"], "may_publish": False},
    "creator_analyst": {"reads": ["public_creator_posts", "public_trader_discussions"], "writes": ["creator_patterns", "problem_clusters"], "may_publish": False},
    "trade_critic": {"reads": ["timestamped_market_snapshots", "prediction_outcomes"], "writes": ["risk_review", "forecast_evaluation"], "may_publish": False},
    "writer": {"reads": ["approved_research_brief", "editorial_memory"], "writes": ["draft"], "may_publish": False},
    "quality_reviewer": {"reads": ["draft", "source_evidence", "visual_validation"], "writes": ["quality_report"], "may_publish": False},
    "founder_partner": {"reads": ["validated_problem_clusters", "experiment_results"], "writes": ["product_hypotheses", "validation_plan"], "may_publish": False},
}

@dataclass(frozen=True)
class Task:
    task_id: str
    goal: str
    role: str
    inputs: dict[str, Any]
    expected_output: str
    external_action: bool = False


def plan_task(task_id: str, goal: str, role: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a requested task and return a small auditable task contract."""
    if role not in ROLES:
        raise ValueError(f"Unknown NIC role: {role}")
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("A non-empty goal is required")
    task = Task(task_id=task_id.strip(), goal=goal.strip(), role=role,
                inputs=inputs if isinstance(inputs, dict) else {},
                expected_output=ROLES[role]["writes"][0], external_action=False)
    return {"schema_version": "nic-agent-task-1.0", **asdict(task),
            "role_contract": ROLES[role], "requires_human_approval": False,
            "provider": "UNCONFIGURED", "status": "PLANNED_NOT_EXECUTED"}


def authorize_action(action: str, approval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fail closed for external side effects; planning never equals permission."""
    approval = approval if isinstance(approval, dict) else {}
    approved = approval.get("approved") is True and bool(str(approval.get("approved_by") or "").strip())
    if action in {"publish_binance_square", "place_trade", "transfer_funds", "withdraw_funds", "change_secrets"}:
        return {"allowed": False, "status": "EXPLICIT_APPROVAL_AND_SEPARATE_GATE_REQUIRED",
                "action": action, "approval_record_present": approved}
    return {"allowed": False, "status": "NO_ACTION_EXECUTOR_CONFIGURED", "action": action}


def learning_record(*, source_url: str, captured_at: str, observation: str,
                    interpretation: str, confidence: float, evaluation: str = "PENDING") -> dict[str, Any]:
    """Create provenance-rich memory; do not convert unverified claims to facts."""
    if not source_url.startswith(("https://", "http://")):
        raise ValueError("A source URL is required for a learning record")
    if not captured_at.strip() or not observation.strip() or not interpretation.strip():
        raise ValueError("capture time, observation, and interpretation are required")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return {"schema_version": "nic-learning-record-1.0", "source_url": source_url,
            "captured_at": captured_at, "recorded_at": datetime.now(timezone.utc).isoformat(),
            "observation": observation, "interpretation": interpretation,
            "confidence": float(confidence), "evaluation": evaluation,
            "verified_fact": False, "status": "NEEDS_EVALUATION"}


def provider_config(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Report safe provider configuration without exposing secrets."""
    env = env or {}
    provider = str(env.get("NIC_LLM_PROVIDER", "NIC_NATIVE")).strip().upper()
    if provider not in {"NIC_NATIVE", "ANTHROPIC_API", "OPENAI_API_COMPATIBLE"}:
        return {"provider": "UNCONFIGURED", "ready": False, "reason": "Unsupported provider"}
    key_name = {"NIC_NATIVE": None, "ANTHROPIC_API": "ANTHROPIC_API_KEY",
                "OPENAI_API_COMPATIBLE": "OPENAI_API_KEY"}[provider]
    ready = provider == "NIC_NATIVE" or bool(env.get(key_name or ""))
    return {"provider": provider, "ready": ready, "credential_name": key_name,
            "secret_value_exposed": False,
            "note": "Provider selection alone does not grant publishing or trading authority."}
