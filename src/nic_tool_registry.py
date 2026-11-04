"""Bounded, read-only tools exposed to NIC's owner-operated agent runtime.

This module deliberately grants no publication, account, secret, filesystem-write,
or arbitrary command authority. Every tool reads a fixed allowlisted artifact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS: dict[str, dict[str, Any]] = {
    "get_agent_registry": {
        "description": "Read NIC specialist roles, their workflow wiring, and honest integration states.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_creator_dashboard": {
        "description": "Read the latest creator command-center summary and evidence status.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_recent_research": {
        "description": "List a small sample of locally persisted research reports and metadata.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_latest_publication": {
        "description": "Read the latest exact-ID Binance Square publication record; does not publish anything.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_reward_learning_status": {
        "description": "Read verified and owner-reported reward-learning totals, coverage, and blockers separately.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_creator_period_coverage": {
        "description": "Read creator-week reward cohort coverage and 7/14-day post-window completeness without attributing weekly totals to posts.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_creator_study_queue": {
        "description": "List a bounded sample of creator profiles NIC is studying, with public engagement clearly separated from earnings.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_reward_pattern_insights": {
        "description": "Read bounded content-format and hook observations from NIC's reward pattern lab, keeping owner-reported and verified reward evidence separate.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class ToolExecutionError(ValueError):
    """Raised when a tool request is invalid or its evidence is unavailable."""


def tool_catalog() -> list[dict[str, Any]]:
    """Return a JSON-serializable allowlist suitable for a model tool declaration."""
    return [{"name": name, **definition} for name, definition in TOOLS.items()]


def _read_json(relative_path: str) -> dict[str, Any]:
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ToolExecutionError(f"evidence_unavailable:{relative_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ToolExecutionError(f"evidence_unreadable:{relative_path}") from exc
    if not isinstance(payload, dict):
        raise ToolExecutionError(f"evidence_invalid_shape:{relative_path}")
    return payload


def _read_jsonl_tail(relative_path: str, limit: int = 5) -> list[dict[str, Any]]:
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ToolExecutionError(f"evidence_unavailable:{relative_path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ToolExecutionError(f"evidence_unreadable:{relative_path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            row = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def execute_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute one allowlisted read-only tool; reject unknown or extra arguments."""
    if name not in TOOLS:
        raise ToolExecutionError("tool_not_allowed")
    args = {} if arguments is None else arguments
    if not isinstance(args, dict) or args:
        raise ToolExecutionError("tool_arguments_not_supported")

    if name == "get_agent_registry":
        data = _read_json("data/live/nic_agent_registry.json")
        agents = data.get("agents", [])
        return {
            "source": "data/live/nic_agent_registry.json",
            "generated_at": data.get("generated_at"),
            "mission": data.get("mission"),
            "agent_count": data.get("agent_count", len(agents) if isinstance(agents, list) else None),
            "operational_agent_count": data.get("operational_agent_count"),
            "agents": [
                {"agent_id": a.get("agent_id"), "name": a.get("name"),
                 "state": a.get("state"), "skills": a.get("skills", []),
                 "limitations": a.get("limitations", [])}
                for a in agents if isinstance(a, dict)
            ] if isinstance(agents, list) else [],
            "policy": data.get("policy", {}),
        }

    if name == "get_creator_dashboard":
        data = _read_json("data/live/nic_dashboard.json")
        return {
            "source": "data/live/nic_dashboard.json",
            "generated_at": data.get("generated_at"),
            "symbol": (data.get("current_decision") or {}).get("symbol"),
            "last_run_id": (data.get("transparent_trace") or {}).get("run_id"),
            "publication": (data.get("transparent_trace") or {}).get("outcome", {}),
            "keys": sorted(data.keys())[:60],
            "summary": {
                key: data[key] for key in (
                    "status", "publication_status", "last_publication",
                    "reward_learning_status", "verified_reward_events",
                    "quality_gate_status",
                ) if key in data and isinstance(data[key], (str, int, float, bool, type(None)))
            },
        }

    if name == "list_recent_research":
        directory = ROOT / "data" / "reports"
        if not directory.is_dir():
            raise ToolExecutionError("evidence_unavailable:data/reports")
        reports = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.name, reverse=True)[:8]:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                reports.append({
                    "file": path.name,
                    "title": str(item.get("title") or item.get("headline") or path.stem)[:240],
                    "keys": sorted(item.keys())[:24],
                })
        return {"source": "data/reports/*.json", "sample_count": len(reports), "reports": reports}

    if name == "get_latest_publication":
        rows = _read_jsonl_tail("analytics/publication_log.jsonl", limit=5)
        if not rows:
            raise ToolExecutionError("publication_history_empty")
        row = rows[-1]
        post_id = str(row.get("canonical_post_id") or row.get("post_id") or "").strip()
        proof = str(row.get("publication_proof") or "")
        verified = row.get("publication_id_verified") is True and bool(post_id) and proof == "binance_openapi_response_post_id"
        return {
            "source": "analytics/publication_log.jsonl",
            "timestamp": row.get("published_at") or row.get("timestamp"),
            "status": row.get("status"),
            "post_id": post_id or None,
            "link": row.get("link"),
            "symbol": row.get("symbol"),
            "category": row.get("category"),
            "content_format": row.get("content_format"),
            "visual_attached": row.get("visual_attached") is True,
            "publication_id_verified": verified,
            "publication_proof": proof or None,
            "monetization_status": (row.get("monetization") or {}).get("status"),
            "reward_amount_usdc": (row.get("monetization") or {}).get("reward_amount_usdc"),
            "reward_is_verified": (row.get("monetization") or {}).get("revenue_verified") is True,
        }

    if name == "get_reward_learning_status":
        data = _read_json("data/intelligence/nic_square_earnings_learning_report.json")
        learning = _read_json("data/live/nic_square_earnings_learning.json")
        feedback = learning.get("owner_reported_reward_feedback")
        feedback = feedback if isinstance(feedback, dict) else {}
        raw_entries = feedback.get("entries")
        entries = []
        if isinstance(raw_entries, list):
            for item in raw_entries[:20]:
                if not isinstance(item, dict):
                    continue
                entries.append({
                    "post_id": item.get("post_id"),
                    "post_url": item.get("public_post_url"),
                    "reported_reward_usdc": item.get("reported_reward_usdc"),
                    "currency": item.get("currency"),
                    "reported_at": item.get("reported_at"),
                    "content_lane": item.get("content_lane"),
                    "content_format": item.get("content_format"),
                    "hook_type": item.get("hook_type"),
                    "summary": item.get("summary"),
                    "owner_reported_views": item.get("owner_reported_views"),
                    "verification_status": item.get("verification_status"),
                    "evidence_type": item.get("evidence_type"),
                })
        fields = (
            "generated_at", "status", "weekly_goal_usdc",
            "verified_reward_events_7d", "verified_usdc_7d",
            "owner_reported_usdc_7d", "owner_reported_events_7d",
            "owner_reported_usdc_14d", "owner_reported_events_14d",
            "owner_reported_posts_14d", "owner_reported_feedback_status",
            "coverage_status", "creator_profiles_resolved",
            "profile_posts_collected_14d", "profile_research_status",
            "autonomy_status", "autonomy_critical_blockers",
            "autonomy_blocker_ids", "autopublish_enabled",
        )
        return {
            "source": "data/intelligence/nic_square_earnings_learning_report.json",
            "summary": {key: data[key] for key in fields if key in data},
            "owner_reported_reward_feedback": {
                "status": feedback.get("status"),
                "accepted_report_count": feedback.get("accepted_report_count"),
                "rejected_report_count": feedback.get("rejected_report_count"),
                "7_day": feedback.get("7_day", {}),
                "14_day": feedback.get("14_day", {}),
                "entries_returned": len(entries),
                "entries": entries,
            },
            "evidence_policy": {
                "owner_reported_is_independent_verification": False,
                "owner_reported_entries_are_post_level_learning_feedback": True,
                "public_views_or_engagement_are_earnings": False,
                "creator_period_totals_attribute_to_individual_posts": False,
            },
        }

    if name == "get_creator_period_coverage":
        data = _read_json("data/intelligence/creator_period_learning.json")
        coverage = data.get("coverage", {})
        periods = data.get("creator_periods", [])
        summaries = []
        if isinstance(periods, list):
            for item in periods[:12]:
                if not isinstance(item, dict):
                    continue
                profile = item.get("profile") or {}
                reward = item.get("creator_period_reward") or {}
                summaries.append({
                    "creator": item.get("creator"),
                    "identity_match": profile.get("identity_match"),
                    "collection_status": profile.get("collection_status"),
                    "window_7d_complete": profile.get("window_7d_complete") is True,
                    "window_14d_complete": profile.get("window_14d_complete") is True,
                    "window_pre_period_14d_complete": profile.get("window_pre_period_14d_complete") is True,
                    "reward_amount": reward.get("amount"),
                    "reward_currency": reward.get("currency"),
                    "reward_period_start": reward.get("period_start"),
                    "reward_period_end": reward.get("period_end"),
                    "posts_7d": (item.get("post_cohort_7d") or {}).get("post_count"),
                    "posts_14d": (item.get("post_cohort_14d") or {}).get("post_count"),
                })
        return {
            "source": "data/intelligence/creator_period_learning.json",
            "learning_status": data.get("learning_status"),
            "coverage_status": data.get("coverage_status"),
            "reward_granularity": data.get("reward_granularity"),
            "coverage": coverage,
            "creators": summaries,
            "attribution_policy": "Creator-period rewards are cohort-level evidence and are never assigned to individual posts.",
        }

    if name == "get_reward_pattern_insights":
        data = _read_json("data/live/nic_revenue_pattern_lab.json")
        observations = data.get("observations", [])
        patterns = []
        if isinstance(observations, list):
            for item in observations:
                if not isinstance(item, dict):
                    continue
                owner_count = item.get("owner_reported_posts", 0)
                verified_count = item.get("verified_posts", 0)
                if not owner_count and not verified_count:
                    continue
                examples = item.get("owner_reported_examples", [])
                patterns.append({
                    "content_lane": item.get("content_lane"),
                    "content_format": item.get("content_format"),
                    "hook_type": item.get("hook_type"),
                    "observed_posts": item.get("posts"),
                    "verified_posts": verified_count,
                    "verified_revenue_usdc": item.get("verified_revenue"),
                    "owner_reported_posts": owner_count,
                    "owner_reported_revenue_usdc": item.get("owner_reported_revenue_usdc"),
                    "owner_reported_evidence": item.get("owner_reported_evidence"),
                    "owner_reported_examples": [
                        {
                            "post_id": example.get("post_id"),
                            "summary": example.get("summary"),
                            "public_post_url": example.get("public_post_url"),
                            "evidence": example.get("evidence"),
                        }
                        for example in examples[:5] if isinstance(example, dict)
                    ] if isinstance(examples, list) else [],
                })
        return {
            "source": "data/live/nic_revenue_pattern_lab.json",
            "status": data.get("status"),
            "generated_at": data.get("generated_at"),
            "verified_observation_groups": data.get("verified_observation_groups"),
            "owner_reported_reward_events_loaded": data.get("owner_reported_reward_events_loaded"),
            "patterns_returned": len(patterns[:12]),
            "patterns": patterns[:12],
            "next_experiments": data.get("next_experiments", [])[:8],
            "evidence_policy": {
                "owner_reported_patterns_are_independently_verified": False,
                "public_views_are_reward_evidence": False,
                "creator_period_totals_are_individual_post_rewards": False,
                "use": "Directional hypotheses only; require fresh NIC post outcomes before changing content policy.",
            },
        }

    if name == "list_creator_study_queue":
        data = _read_json("data/live/nic_square_earnings_learning.json")
        queue = data.get("creator_study_queue", [])
        creators = []
        if isinstance(queue, list):
            for item in queue[:10]:
                if not isinstance(item, dict):
                    continue
                creators.append({
                    "creator": item.get("creator"),
                    "discovery_window_days": item.get("discovery_window"),
                    "posts_observed": item.get("posts_observed"),
                    "dominant_archetypes": item.get("dominant_archetypes", []),
                    "public_engagement_rate": item.get("public_engagement_rate"),
                    "median_views": item.get("median_views"),
                    "earnings_status": item.get("earnings_status"),
                    "discovery_signal": item.get("discovery_signal"),
                    "sample_urls": item.get("sample_urls", [])[:5],
                })
        return {
            "source": "data/live/nic_square_earnings_learning.json",
            "research_coverage": data.get("research_coverage", {}),
            "creator_count_returned": len(creators),
            "creators": creators,
            "policy": "Public engagement is a research signal, not evidence of earnings.",
        }

    raise ToolExecutionError("tool_not_allowed")
