"""Bounded, read-only tools exposed to NIC's owner-operated agent runtime.

This module deliberately grants no publication, account, secret, filesystem-write,
or arbitrary command authority. Every tool reads a small allowlisted artifact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS: dict[str, dict[str, Any]] = {
    "get_agent_registry": {
        "description": "Read the latest generated NIC specialist-agent registry and its real integration states.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_creator_dashboard": {
        "description": "Read the latest creator dashboard summary, including publication and reward-learning evidence status.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_recent_research": {
        "description": "List a small sample of locally persisted research reports and their available metadata.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class ToolExecutionError(ValueError):
    """Raised when a tool request is invalid or its evidence is unavailable."""


def tool_catalog() -> list[dict[str, Any]]:
    """Return a JSON-serializable allowlist suitable for a model tool declaration."""
    return [
        {"name": name, **definition}
        for name, definition in TOOLS.items()
    ]


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
                {
                    "agent_id": a.get("agent_id"),
                    "name": a.get("name"),
                    "state": a.get("state"),
                    "limitations": a.get("limitations", []),
                }
                for a in agents if isinstance(a, dict)
            ] if isinstance(agents, list) else [],
            "policy": data.get("policy", {}),
        }

    if name == "get_creator_dashboard":
        data = _read_json("data/live/nic_dashboard.json")
        # Keep the response bounded and avoid returning arbitrary nested artifacts.
        return {
            "source": "data/live/nic_dashboard.json",
            "keys": sorted(data.keys())[:60],
            "summary": {
                key: data[key] for key in (
                    "status", "generated_at", "publication_status",
                    "last_publication", "reward_learning_status",
                    "verified_reward_events", "quality_gate_status",
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

    raise ToolExecutionError("tool_not_allowed")
