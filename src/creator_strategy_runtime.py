"""Creator-strategy runtime: load the NIC playbook, annotate drafts, and block repeated openings.

This module records what strategy artifact the generator actually consumed. It does not
claim creator-reward learning unless independently attributed reward evidence exists.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_PATH = ROOT / "data/intelligence/creator_strategy_playbook.json"
PERIOD_LEARNING_PATH = ROOT / "data/intelligence/creator_period_learning.json"
PUBLICATION_LOG = ROOT / "analytics/publication_log.jsonl"
PLAYBOOK_FALLBACK_VERSION = "missing-playbook"


def _load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError, TypeError):
        return default


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split())


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", str(text).strip(), maxsplit=1)
    return _normalize(parts[0] if parts else text)


def _recent_openings(limit: int = 12) -> set[str]:
    openings: set[str] = set()
    if not PUBLICATION_LOG.exists():
        return openings
    try:
        rows = PUBLICATION_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return openings
    for row in rows:
        try:
            item = json.loads(row)
        except ValueError:
            continue
        body = item.get("text") or item.get("post") or item.get("content") or ""
        opening = _first_sentence(str(body))
        if len(opening.split()) >= 5:
            openings.add(opening)
    return openings


def prepare_context(context: dict[str, Any]) -> dict[str, Any]:
    """Attach the playbook and immutable version metadata before writing."""
    playbook = _load_json(PLAYBOOK_PATH, {})
    if not playbook:
        raise RuntimeError(f"Creator strategy playbook missing or invalid: {PLAYBOOK_PATH}")
    digest = hashlib.sha256(PLAYBOOK_PATH.read_bytes()).hexdigest()
    preflight = context.get("preflight") or {}
    selected = preflight.get("selected_opportunity") or {}
    director = preflight.get("script_director_4") or {}
    category = str(selected.get("category") or "market_opportunity").lower()
    story_type = str(
        director.get("story_type")
        or selected.get("story_type")
        or director.get("narrative_engine")
        or "research_edge"
    ).lower().replace(" ", "_")
    # A fit-based strategy label is metadata, not a forced prose template.
    if category in {"breaking_news", "news", "news_and_macro", "macro"}:
        strategy_id = "catalyst_context_and_counterpoint"
    elif category in {"research_insight", "research_only", "no_trade"}:
        strategy_id = "evidence_led_research"
    elif story_type in {"breakout_retest", "range_structure", "trend_continuation"}:
        strategy_id = "structure_and_confirmation"
    elif story_type in {"momentum_volume", "relative_strength"}:
        strategy_id = "participation_and_relative_strength"
    else:
        strategy_id = "asset_specific_research_edge"
    period_learning = _load_json(PERIOD_LEARNING_PATH, {})
    learning_status = str(period_learning.get("learning_status") or "NOT_AVAILABLE")
    period_digest = hashlib.sha256(PERIOD_LEARNING_PATH.read_bytes()).hexdigest() if PERIOD_LEARNING_PATH.exists() else None
    # The reward is creator-period aggregate evidence. Only descriptive cohort
    # observations may be exposed to generation; never attach reward to a post.
    context["creator_strategy_playbook"] = playbook
    context["creator_period_learning"] = period_learning if learning_status == "COHORT_HYPOTHESES_READY" else {}
    context["creator_strategy_runtime"] = {
        "status": "LOADED",
        "playbook_schema_version": playbook.get("schema_version"),
        "playbook_sha256": digest,
        "strategy_id": strategy_id,
        "selected_category": category,
        "selected_story_type": story_type,
        "loaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "reward_learning_claim": "NOT_CLAIMED",
        "creator_period_learning_status": learning_status,
        "creator_period_learning_sha256": period_digest,
        "creator_period_learning_used": learning_status == "COHORT_HYPOTHESES_READY",
        "reward_granularity": "creator_period_only",
    }
    return context


def annotate_and_validate(result: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Record strategy provenance and stop exact repeated opening lines."""
    runtime = context.get("creator_strategy_runtime") or {}
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    post = str(draft.get("text") or draft.get("post") or draft.get("body") or "").strip()
    if not post:
        raise RuntimeError("Creator strategy validation: generated draft has no text")
    opening = _first_sentence(post)
    duplicate = bool(opening and opening in _recent_openings())
    gate = {
        "status": "REJECTED_DUPLICATE_OPENING" if duplicate else "PASSED",
        "duplicate_opening": duplicate,
        "opening_fingerprint": hashlib.sha256(opening.encode("utf-8")).hexdigest() if opening else None,
        "checks": ["playbook_loaded", "strategy_provenance_recorded", "recent_opening_duplicate_check"],
    }
    draft["creator_strategy_id"] = runtime.get("strategy_id")
    draft["creator_strategy_playbook_sha256"] = runtime.get("playbook_sha256")
    draft["creator_strategy_version"] = runtime.get("playbook_schema_version")
    draft["creator_period_learning_status"] = runtime.get("creator_period_learning_status", "NOT_AVAILABLE")
    draft["creator_period_learning_sha256"] = runtime.get("creator_period_learning_sha256")
    draft["creator_period_learning_used"] = bool(runtime.get("creator_period_learning_used"))
    draft["reward_granularity"] = "creator_period_only"
    draft["creator_strategy_quality_gate"] = gate
    result["draft"] = draft
    result["creator_strategy_runtime"] = runtime
    result["creator_strategy_quality_gate"] = gate
    if duplicate:
        raise RuntimeError(
            "Creator strategy quality gate rejected a repeated opening from recent publication history; "
            "draft was not approved for publication."
        )
    return result
