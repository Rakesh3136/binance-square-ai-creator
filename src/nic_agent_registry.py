"""NIC specialist registry and capability truth report.

This registry describes real repository modules and their current integration
state. It does not create fake agents, start workers, or grant publication
authority. Only the canonical workflow and publisher own runtime execution.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/autonomous-market-creator.yml"
OUT = ROOT / "data/live/nic_agent_registry.json"

REGISTRY = [
    {
        "agent_id": "research",
        "name": "Research Agent",
        "purpose": "Collect market, project, macro, and public creator evidence.",
        "skills": ["news_research", "original_research", "creator_profile_research", "weekly_earner_study"],
        "modules": ["news_scanner.py", "original_research_engine.py", "nic_square_profile_research.py", "nic_weekly_earner_study.py"],
        "workflow_entrypoints": ["news_scanner.py", "original_research_engine.py", "nic_square_profile_research.py", "nic_weekly_earner_study.py"],
        "state": "workflow_wired",
        "limitations": ["External source access and completeness remain evidence-dependent."],
    },
    {
        "agent_id": "market_analysis",
        "name": "Market Analysis Agent",
        "purpose": "Interpret current market snapshots, flows, and conditional setups for creator content.",
        "skills": ["market_scanning", "capital_flow_analysis", "regime_context", "risk_invalidation"],
        "modules": ["live_market_scanner.py", "capital_flow_intelligence.py", "nic_prediction_engine.py"],
        "workflow_entrypoints": ["live_market_scanner.py", "capital_flow_intelligence.py", "nic_prediction_engine.py"],
        "state": "workflow_wired",
        "limitations": ["Decision support only; this role has no trading or order authority."],
    },
    {
        "agent_id": "writing_editorial",
        "name": "Writing and Editorial Agent",
        "purpose": "Turn evidence into original creator posts and apply editorial review.",
        "skills": ["content_planning", "native_drafting", "editing", "originality_review", "deduplication"],
        "modules": ["candidate_generation_4.py", "safe_creator_runner.py", "multi_agent_creator.py", "nic_native_writer.py", "human_editor.py", "recent_sentence_deduplicator.py"],
        "workflow_entrypoints": ["candidate_generation_4.py", "safe_creator_runner.py", "human_editor.py", "recent_sentence_deduplicator.py"],
        "state": "workflow_wired",
        "limitations": ["The native writer is a bounded deterministic writing engine, not an independent model-backed agent."],
    },
    {
        "agent_id": "visual",
        "name": "Visual and Chart Agent",
        "purpose": "Render chart assets and validate visual alignment with the approved story.",
        "skills": ["chart_rendering", "visual_composition", "visual_validation"],
        "modules": ["visual_renderer.py", "market_chart_renderer.py", "validate_visual.py", "validate_trade_visual_contract.py"],
        "workflow_entrypoints": ["visual_renderer.py", "validate_visual.py", "validate_trade_visual_contract.py"],
        "state": "workflow_wired",
        "limitations": ["Chart rendering is present; a general-purpose image-generation service is not proven integrated."],
    },
    {
        "agent_id": "publication",
        "name": "Publication Agent",
        "purpose": "Publish only drafts authorized by all authoritative quality, eligibility, and control gates.",
        "skills": ["publication_authorization", "duplicate_prevention", "binance_square_publish", "publication_proof"],
        "modules": ["nic_publication_authorization.py", "write_to_earn_eligibility_gate.py", "binance_square_publisher.py", "nic_publication_proof_audit.py"],
        "workflow_entrypoints": ["nic_publication_authorization.py", "write_to_earn_eligibility_gate.py", "binance_square_publisher.py", "nic_publication_proof_audit.py"],
        "state": "workflow_wired",
        "limitations": ["Publisher is the sole publication authority; other roles must not receive publishing credentials."],
    },
    {
        "agent_id": "learning_rewards",
        "name": "Performance and Reward Learning Agent",
        "purpose": "Collect post outcomes, creator-period evidence, reward events, and strategy feedback.",
        "skills": ["post_performance_collection", "reward_evidence_reconciliation", "creator_period_learning", "experiment_feedback"],
        "modules": ["square_performance_collector.py", "nic_square_earnings_learning.py", "nic_creator_period_learning.py", "nic_outcome_learner.py"],
        "workflow_entrypoints": ["square_performance_collector.py", "nic_square_earnings_learning.py", "nic_outcome_learner.py"],
        "state": "workflow_wired",
        "limitations": ["Creator-week totals are cohort evidence, not proof of an individual post payout."],
    },
    {
        "agent_id": "audience_analytics",
        "name": "Audience Analytics Agent",
        "purpose": "Summarize audience engagement and content performance signals.",
        "skills": ["engagement_metrics", "audience_response_analysis"],
        "modules": ["engagement_engine.py", "audience_intelligence.py"],
        "workflow_entrypoints": [],
        "state": "module_present_not_proven_in_canonical_workflow",
        "limitations": ["Analytics modules exist; no end-to-end reply-reading and reply-publishing capability is established."],
    },
    {
        "agent_id": "community_replies",
        "name": "Community Reply Agent",
        "purpose": "Read comments and prepare contextual, moderated replies for the creator.",
        "skills": ["comment_collection", "contextual_reply_drafting", "moderation"],
        "modules": [],
        "workflow_entrypoints": [],
        "state": "not_implemented",
        "limitations": ["No complete, tested comment-to-reply-to-publication path is registered."],
    },
    {
        "agent_id": "chat_operator",
        "name": "NIC Chat Operator",
        "purpose": "Provide the existing authenticated chat and owner-control API.",
        "skills": ["assistant_chat", "owner_control_api", "bounded_read_only_tool_execution", "agent_registry_read", "publication_audit_read", "reward_learning_read", "creator_cohort_read", "research_queue_read", "reward_pattern_insights_read"],
        "modules": ["nic_assistant_chat.py", "nic_control_gate.py", "nic_tool_registry.py"],
        "workflow_entrypoints": [],
        "state": "service_present_read_only_tools_connected",
        "limitations": ["Chat exposes eight bounded read-only tools; no publication, trading, shell, arbitrary writes, or universal executor integration."],
    },
]


def build_registry() -> dict:
    workflow = WORKFLOW.read_text(encoding="utf-8") if WORKFLOW.exists() else ""
    agents = []
    for definition in REGISTRY:
        modules = definition["modules"]
        missing = [name for name in modules if not (ROOT / "src" / name).is_file()]
        wired = [
            name for name in definition["workflow_entrypoints"]
            if any(f"python src/{name}" in line for line in workflow.splitlines())
        ]
        expected_wiring_missing = [
            name for name in definition["workflow_entrypoints"]
            if name not in wired
        ]
        state = definition["state"]
        if missing:
            state = "registry_invalid_missing_module"
        elif definition["workflow_entrypoints"] and expected_wiring_missing:
            state = "registry_wiring_drift"
        agents.append({
            **definition,
            "state": state,
            "module_count": len(modules),
            "modules_present": not missing,
            "missing_modules": missing,
            "workflow_wired_modules": wired,
            "workflow_wiring_missing": expected_wiring_missing,
            "model_backed_independent_agent": False,
        })
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "autonomous_binance_square_creator",
        "orchestration_authority": ".github/workflows/autonomous-market-creator.yml",
        "publication_authority": "src/binance_square_publisher.py",
        "agent_count": len(agents),
        "operational_agent_count": sum(a["state"] == "workflow_wired" for a in agents),
        "not_implemented_agent_count": sum(a["state"] == "not_implemented" for a in agents),
        "policy": {
            "logical_mesh_nodes_are_not_independent_agents": True,
            "only_publisher_may_publish": True,
            "quality_gates_must_not_be_weakened": True,
            "reward_claims_require_explicit_evidence_class": True,
        },
        "agents": agents,
    }


def main() -> int:
    registry = build_registry()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "OK" if all(not a["missing_modules"] and not a["workflow_wiring_missing"] for a in registry["agents"]) else "NEEDS_REVIEW",
        "agent_count": registry["agent_count"],
        "workflow_wired_count": registry["operational_agent_count"],
        "not_implemented_count": registry["not_implemented_agent_count"],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))
    return 0 if all(not a["missing_modules"] and not a["workflow_wiring_missing"] for a in registry["agents"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
