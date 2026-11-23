"""NIC Design Intelligence: reusable design constraints and safe preview policy.

This module gives NIC a grounded design brief for generating interface proposals.
It does not write files, install builds, change permissions, or publish UI changes.
"""
from __future__ import annotations

from typing import Any

DESIGN_SYSTEM: dict[str, Any] = {
    "product": "NIC — Neural Intelligence Companion",
    "visual_direction": {
        "mood": ["confident", "calm", "technical", "human", "premium"],
        "theme": "dark-first with accessible light-theme support",
        "palette": {
            "background": "#0A0E18",
            "surface": "#141B2B",
            "surface_elevated": "#1B263A",
            "text_primary": "#EEF3FF",
            "text_secondary": "#96A4BE",
            "accent": "#7491FF",
            "success": "#54D6A0",
            "warning": "#FFCD70",
            "danger": "#FF7272",
        },
        "typography": "clear hierarchy, readable body sizes, tabular numerals for metrics",
        "shape": "rounded cards, restrained borders, consistent spacing",
        "motion": "subtle, purposeful, reduced-motion aware",
    },
    "experience_principles": [
        "Make the assistant conversation the primary workspace, not a settings form.",
        "Show what NIC is doing, what it needs, and what it completed.",
        "Keep task timeline, evidence provenance, and permission state visible.",
        "Separate owner controls from ordinary chat and clearly label destructive actions.",
        "Never imply a capability is live unless a connected service confirms it.",
        "Design mobile-first for one-handed Android use and adapt to desktop.",
        "Provide empty, loading, offline, error, and success states for every live panel.",
        "Use accessible contrast, touch targets, focus states, and screen-reader labels.",
    ],
    "primary_navigation": [
        "Home",
        "Assistant",
        "Workspace",
        "Agents",
        "Activity",
        "Creator Studio",
        "Settings",
    ],
    "core_surfaces": [
        {"id": "home", "purpose": "overview, connection health, current tasks, quick actions"},
        {"id": "assistant", "purpose": "chat, voice entry point, attachments, task handoff"},
        {"id": "workspace", "purpose": "browser, files, code editor, terminal, preview windows"},
        {"id": "agents", "purpose": "task-scoped specialist roles, skills, assignments, outcomes"},
        {"id": "activity", "purpose": "append-only event timeline, evidence and approvals"},
        {"id": "creator_studio", "purpose": "research, drafts, visuals, editorial checks, publishing approvals, rewards"},
        {"id": "settings", "purpose": "connections, autonomy scope, security, accessibility"},
    ],
    "preview_policy": {
        "allowed_proposal_roots": ["dashboard/", "android/"],
        "never_modify_without_explicit_owner_approval": [
            "authentication", "authorization", "permission scopes", "emergency stop",
            "secrets", "publishing", "payments", "deployment", "production data",
        ],
        "required_before_approval": [
            "isolated preview", "build or render check", "accessibility review",
            "mobile and desktop layout review", "security diff review",
            "rollback path", "owner-visible change summary",
        ],
        "production_changes": "owner approval required; no silent self-modification",
    },
}


def get_design_guidelines() -> dict[str, Any]:
    """Return a copy-safe, read-only design system and self-improvement policy."""
    import copy
    return copy.deepcopy(DESIGN_SYSTEM)


def build_design_brief(goal: str, surface: str = "assistant") -> dict[str, Any]:
    """Create a bounded design brief for a supported NIC surface."""
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
        raise ValueError("design_goal_invalid")
    valid = {item["id"] for item in DESIGN_SYSTEM["core_surfaces"]}
    if surface not in valid:
        raise ValueError("design_surface_invalid")
    selected = next(item for item in DESIGN_SYSTEM["core_surfaces"] if item["id"] == surface)
    return {
        "product": DESIGN_SYSTEM["product"],
        "surface": selected,
        "goal": goal.strip(),
        "visual_direction": get_design_guidelines()["visual_direction"],
        "principles": list(DESIGN_SYSTEM["experience_principles"]),
        "deliverables": [
            "information architecture",
            "mobile-first screen layout",
            "responsive desktop layout",
            "component and state inventory",
            "accessible interaction specification",
            "isolated preview implementation",
            "test and rollback report",
        ],
        "approval_required_before_production": True,
        "file_write_authority": "none",
    }
