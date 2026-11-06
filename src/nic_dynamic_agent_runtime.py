"""Task-scoped NIC specialist workers.

A specialist is created only for a concrete task, exists for one request, and
receives only a small, role-specific allowlist of bounded read-only tools.
Specialists return findings to the NIC orchestrator; they never answer users,
publish, trade, access secrets, or write files.
"""
from __future__ import annotations

from typing import Any, Callable

SPECIALIST_PROFILES: dict[str, dict[str, Any]] = {
    "research_analyst": {
        "purpose": "Find and summarize existing market, creator, and research evidence.",
        "tools": ["list_recent_research", "list_creator_study_queue", "get_creator_period_coverage"],
    },
    "reward_analyst": {
        "purpose": "Audit reward evidence, attribution boundaries, and creator-period learning.",
        "tools": ["get_reward_learning_status", "get_creator_period_coverage", "get_latest_publication"],
    },
    "performance_auditor": {
        "purpose": "Check publication records and distinguish reach, publication, and verified rewards.",
        "tools": ["get_latest_publication", "get_reward_learning_status"],
    },
    "creator_strategist": {
        "purpose": "Develop creator strategy from creator cohorts, reward feedback, and observed research.",
        "tools": ["list_creator_study_queue", "get_creator_period_coverage", "get_reward_learning_status"],
    },
    "editorial_coach": {
        "purpose": "Improve originality, clarity, structure, audience relevance, and factual caution in draft content.",
        "tools": ["list_recent_research"],
    },
    "fact_checker": {
        "purpose": "Check claims against available publication and research records; flag unsupported claims.",
        "tools": ["list_recent_research", "get_latest_publication"],
    },
}

MAX_TASK_CHARS = 4000
MAX_CONTEXT_CHARS = 8000
MAX_WORKER_TOOL_CALLS = 2


def specialist_catalog() -> list[dict[str, Any]]:
    """Expose only specialist identities and their bounded capabilities."""
    return [
        {"specialty": name, "purpose": profile["purpose"], "tools": list(profile["tools"])}
        for name, profile in SPECIALIST_PROFILES.items()
    ]


def _tool_definitions(catalog: list[dict[str, Any]], allowed: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": item["name"],
            "description": item["description"],
            "parameters": {**item["parameters"], "required": []},
            "strict": True,
        }
        for item in catalog
        if item["name"] in allowed
    ]


def run_specialist(
    *,
    client: Any,
    model: str,
    specialty: str,
    task: str,
    context: str,
    catalog: list[dict[str, Any]],
    execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Create and run one ephemeral specialist; execute only its role allowlist."""
    if specialty not in SPECIALIST_PROFILES:
        raise ValueError("specialist_not_allowed")
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS:
        raise ValueError("specialist_task_invalid")
    if not isinstance(context, str) or len(context) > MAX_CONTEXT_CHARS:
        raise ValueError("specialist_context_invalid")

    profile = SPECIALIST_PROFILES[specialty]
    allowed = set(profile["tools"])
    tools = _tool_definitions(catalog, allowed)
    instructions = (
        "You are an ephemeral NIC specialist worker. Return findings ONLY to the NIC "
        "orchestrator; NEVER respond directly to the user. Work only on the assigned task. "
        "Use the provided read-only tools when relevant. Do not invent missing evidence. "
        "Separate verified rewards, owner-reported rewards, creator-period totals, and "
        "public engagement. Never attribute creator-week totals to individual posts. "
        "Never claim that views prove earnings. You cannot publish, trade, write files, "
        "access secrets, or call tools outside your provided allowlist. Report evidence, "
        "uncertainties, blockers, and a concise recommendation.\n"
        f"Specialty: {specialty}. Purpose: {profile['purpose']}"
    )
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[
            {"role": "user", "content": f"Task:\n{task.strip()}\n\nContext:\n{context.strip()}"},
        ],
        max_output_tokens=900,
        **({"tools": tools, "tool_choice": "auto", "parallel_tool_calls": False} if tools else {}),
    )
    calls_used = 0
    while True:
        output_items = getattr(response, "output", None) or []
        calls = [item for item in output_items if getattr(item, "type", None) == "function_call"]
        if not calls:
            break
        call = calls[0]
        call_id = getattr(call, "call_id", "")
        name = getattr(call, "name", "")
        raw = getattr(call, "arguments", "{}")
        if not call_id:
            raise RuntimeError("specialist_tool_call_missing_id")
        if calls_used >= MAX_WORKER_TOOL_CALLS:
            result: dict[str, Any] = {"ok": False, "error": "specialist_tool_call_limit_reached"}
        else:
            import json
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
                if name not in allowed:
                    raise ValueError("specialist_tool_not_allowed")
                result = {"ok": True, "result": execute_tool(name, args)}
            except (ValueError, TypeError) as exc:
                result = {"ok": False, "error": str(exc)}
        response = client.responses.create(
            model=model,
            instructions=instructions,
            previous_response_id=getattr(response, "id", None),
            input=[{
                "type": "function_call_output",
                "call_id": call_id,
                "output": __import__("json").dumps(result, ensure_ascii=False),
            }],
            max_output_tokens=900,
            **({"tools": tools, "tool_choice": ("none" if calls_used >= MAX_WORKER_TOOL_CALLS else "auto"),
               "parallel_tool_calls": False} if tools else {}),
        )
        calls_used += 1
        if calls_used > MAX_WORKER_TOOL_CALLS:
            break

    answer = getattr(response, "output_text", None)
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("specialist_returned_no_findings")
    return {
        "specialty": specialty,
        "task": task.strip(),
        "status": "completed",
        "tool_allowlist": sorted(allowed),
        "tool_calls_used": calls_used,
        "findings": answer.strip(),
        "user_response_authority": False,
        "publication_authority": False,
        "trading_authority": False,
    }
