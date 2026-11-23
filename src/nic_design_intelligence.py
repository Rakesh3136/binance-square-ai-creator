"""NIC Design Intelligence: reusable design constraints and safe preview policy.

This module gives NIC a grounded design brief for generating interface proposals.
It does not write files, install builds, change permissions, or publish UI changes.
"""
from __future__ import annotations

from typing import Any
from html import escape

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



def render_design_preview(brief: dict[str, Any]) -> str:
    """Render a self-contained, non-interactive HTML proposal for isolated review.

    This function returns HTML only. It never writes files, mutates production UI,
    executes scripts, or changes permissions.
    """
    if not isinstance(brief, dict) or brief.get("approval_required_before_production") is not True:
        raise ValueError("design_brief_invalid")
    surface = brief.get("surface")
    if not isinstance(surface, dict) or surface.get("id") not in {
        item["id"] for item in DESIGN_SYSTEM["core_surfaces"]
    }:
        raise ValueError("design_surface_invalid")
    goal = brief.get("goal")
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
        raise ValueError("design_goal_invalid")

    palette = DESIGN_SYSTEM["visual_direction"]["palette"]
    nav = "".join(
        f'<a href="#{escape(item.lower().replace(" ", "-"))}">{escape(item)}</a>'
        for item in DESIGN_SYSTEM["primary_navigation"]
    )
    safe_goal = escape(goal)
    safe_surface = escape(str(surface["id"]).replace("_", " ").title())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>NIC Design Preview — {safe_surface}</title>
<style>
:root{{--bg:{palette["background"]};--panel:{palette["surface"]};--raised:{palette["surface_elevated"]};--fg:{palette["text_primary"]};--muted:{palette["text_secondary"]};--accent:{palette["accent"]};--ok:{palette["success"]};}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 15% 0%,#1d2b4b 0,transparent 42%),var(--bg);color:var(--fg);font:15px/1.5 Inter,system-ui,sans-serif}}
.shell{{max-width:1180px;margin:auto;padding:24px}}header{{display:flex;justify-content:space-between;align-items:center;gap:16px;border-bottom:1px solid #34415d;padding:12px 0 22px}}
.brand{{font-size:24px;font-weight:800;letter-spacing:-1px}}.tag{{color:var(--muted);font-size:12px}}
nav{{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}}nav a{{color:var(--muted);text-decoration:none;padding:8px 12px;border:1px solid #34415d;border-radius:99px;font-size:12px}}
nav a:first-child{{background:var(--raised);color:var(--fg)}}.hero{{padding:30px 0 22px}}.eyebrow{{color:var(--accent);font-weight:700;font-size:11px;letter-spacing:2px}}
h1{{font-size:clamp(30px,5vw,48px);line-height:1.05;margin:10px 0}}.muted{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(240px,.8fr);gap:16px}}
.card{{background:linear-gradient(145deg,var(--raised),var(--panel));border:1px solid #35435f;border-radius:22px;padding:20px;box-shadow:0 18px 50px #0003}}
.card h2{{font-size:17px;margin:0 0 12px}}.bubble{{background:#263552;border-radius:18px 18px 18px 5px;padding:14px;margin:12px 0;max-width:88%}}
.prompt{{border:1px solid #455573;border-radius:15px;padding:14px;color:var(--muted);margin-top:18px}}
.pill{{display:inline-block;border-radius:99px;padding:5px 10px;background:#1d3c39;color:var(--ok);font-size:11px;font-weight:700}}
.metric{{font-size:28px;font-weight:800}}.stack{{display:grid;gap:12px}}.foot{{margin-top:16px;font-size:11px;color:var(--muted)}}
@media(max-width:700px){{.shell{{padding:16px}}header{{align-items:flex-start;flex-direction:column}}.grid{{grid-template-columns:1fr}}nav{{flex-wrap:nowrap;overflow:auto;padding-bottom:6px}}nav a{{white-space:nowrap}}}}
</style></head>
<body><main class="shell">
<header><div><div class="brand">✦ NIC <span class="tag">NEURAL INTELLIGENCE COMPANION</span></div><div class="tag">A calmer, clearer workspace for your AI</div></div><span class="pill">DESIGN PREVIEW · NOT LIVE</span></header>
<nav>{nav}</nav>
<section class="hero"><div class="eyebrow">DESIGN INTELLIGENCE / PROPOSAL</div><h1>Your ideas,<br>moving forward.</h1><p class="muted">A unified workspace for conversation, research, specialist agents and owner-controlled actions.</p></section>
<section class="grid"><article class="card"><div class="eyebrow">ASSISTANT WORKSPACE</div><h2>Good to see you.</h2><p class="muted">What would you like NIC to work on?</p><div class="bubble">I can research a topic, prepare a draft, or help plan a project. I'll explain actions and ask before sensitive changes.</div><div class="prompt">Message NIC… <span style="float:right;color:var(--accent)">➤</span></div></article>
<aside class="stack"><div class="card"><div class="eyebrow">SYSTEM STATUS</div><h2>Everything in view</h2><div class="metric">Ready</div><p class="muted">Connection state is shown only when confirmed by the service.</p></div><div class="card"><div class="eyebrow">OWNER CONTROL</div><h2>You're in control</h2><p class="muted">Review permissions, pending approvals and the emergency stop from one place.</p><span class="pill">APPROVAL REQUIRED</span></div></aside></section>
<section class="card" style="margin-top:16px"><div class="eyebrow">CURRENT DESIGN GOAL</div><h2>{safe_goal}</h2><p class="muted">Preview surface: {safe_surface}. This is a static concept, not a connected or production interface.</p></section>
<p class="foot">NIC Design Intelligence · Isolated HTML preview · No production files changed · Owner approval required before release</p>
</main></body></html>"""
