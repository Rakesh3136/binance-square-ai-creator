"""Bounded self-improvement for NIC's native editorial writer.

Generate a small, deterministic set of genuinely different presentations of the
same frozen evidence, score them with transparent checks, and keep one draft.
This is candidate selection, not reward prediction; publication gates remain
authoritative and the system never loops indefinitely.
"""
from __future__ import annotations

import copy
import re
from difflib import SequenceMatcher
from typing import Callable, Any

MAX_CANDIDATES = 4
RECENT_POST_SIMILARITY_BLOCK = 0.88
RECENT_PUBLICATION_LOG = __import__("pathlib").Path(__file__).resolve().parents[1] / "analytics" / "publication_log.jsonl"
PRESENTATION_STRATEGIES = (
    "asset_specific_research_edge",
    "evidence_led_research",
    "structure_and_confirmation",
    "participation_and_relative_strength",
)
UNSAFE_CLAIMS = (
    "guaranteed profit", "guaranteed return", "will definitely pump",
    "risk-free", "certain to rise", "100% sure",
)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(text).lower()).split())


def _token_jaccard(left: str, right: str) -> float:
    a = set(_normalize(left).split())
    b = set(_normalize(right).split())
    return len(a & b) / len(a | b) if a and b else 0.0


def _recent_publication_texts(context: dict[str, Any]) -> list[str]:
    # Tests and controlled callers may inject a frozen history; production reads
    # the persisted publication log used by the final originality gate.
    injected = context.get("recent_publication_texts")
    if isinstance(injected, list):
        return [str(x).strip() for x in injected if isinstance(x, str) and x.strip()]
    if not RECENT_PUBLICATION_LOG.exists():
        return []
    rows = []
    for line in RECENT_PUBLICATION_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]:
        try:
            item = __import__("json").loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("post") or item.get("content") or "").strip()
        if text:
            rows.append(text)
    return rows


def score_candidate(result: dict[str, Any], context: dict[str, Any],
                    previous_texts: list[str] | None = None,
                    recent_publication_texts: list[str] | None = None) -> dict[str, Any]:
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    post = str(draft.get("post") or draft.get("text") or "").strip()
    symbol = str(draft.get("symbol") or "").upper().replace("USDT", "").strip()
    normalized = _normalize(post)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", post) if s.strip()]
    questions = post.count("?")
    issues = []
    if not post:
        issues.append("missing_text")
    if not symbol or f"\u0024{symbol.lower()}" not in post.lower():
        issues.append("missing_frozen_asset")
    if not 280 <= len(post) <= 700:
        issues.append("length_out_of_bounds")
    if questions != 1:
        issues.append("must_have_exactly_one_reader_question")
    if any(_normalize(term) in normalized for term in UNSAFE_CLAIMS):
        issues.append("unsupported_earnings_or_certainty_claim")
    if len(sentences) < 3:
        issues.append("insufficient_structure")

    score = 0.0
    score += 25 if not issues else max(0, 25 - 8 * len(issues))
    score += 20 if symbol and f"\u0024{symbol.lower()}" in post.lower() else 0
    unique_ratio = len({_normalize(s) for s in sentences}) / max(1, len(sentences))
    score += 20 * unique_ratio
    score += 15 if questions == 1 else 0
    score += min(10, 5 * len(re.findall(r"\d+(?:\.\d+)?%?", post)))
    max_similarity = max(
        (SequenceMatcher(None, normalized, _normalize(old)).ratio()
         for old in (previous_texts or [])), default=0.0
    )
    score += 10 * (1.0 - max_similarity)
    if max_similarity >= 0.82:
        issues.append("near_duplicate_of_another_candidate")

    history = recent_publication_texts if recent_publication_texts is not None else _recent_publication_texts(context)
    max_recent_similarity = max((_token_jaccard(post, old) for old in history), default=0.0)
    # Match the production NIC 21 originality gate's token-set Jaccard metric.
    # This is an early candidate-selection guard, not a replacement for final gates.
    if max_recent_similarity >= RECENT_POST_SIMILARITY_BLOCK:
        issues.append("near_duplicate_of_recent_publication")
    score += 10 * (1.0 - max_recent_similarity)
    return {
        "score": round(score, 2),
        "eligible": not issues,
        "issues": issues,
        "character_count": len(post),
        "sentence_count": len(sentences),
        "question_count": questions,
        "max_similarity_to_other_candidate": round(max_similarity, 4),
        "max_similarity_to_recent_publication": round(max_recent_similarity, 4),
        "presentation_strategy": result.get("iteration_presentation_strategy"),
    }


def generate_and_select(context: dict[str, Any],
                        build: Callable[[dict[str, Any]], dict[str, Any]],
                        max_candidates: int = MAX_CANDIDATES) -> dict[str, Any]:
    """Build <=4 alternatives from identical evidence, then select one safely."""
    budget = max(1, min(int(max_candidates), MAX_CANDIDATES))
    candidates = []
    errors = []
    for index, strategy in enumerate(PRESENTATION_STRATEGIES[:budget]):
        variant_context = copy.deepcopy(context)
        variant_context["iteration_seed"] = index
        variant_context["iteration_strategy_id"] = strategy
        try:
            result = build(variant_context)
            if not isinstance(result, dict):
                raise TypeError("writer returned a non-object result")
            result["iteration_presentation_strategy"] = strategy
            result["iteration_seed"] = index
            candidates.append(result)
        except Exception as exc:
            errors.append({"candidate_index": index, "strategy": strategy,
                           "error": str(exc)[:300]})

    scored = []
    texts = []
    recent_texts = _recent_publication_texts(context)
    for result in candidates:
        report = score_candidate(result, context, texts, recent_texts)
        text = str((result.get("draft") or {}).get("post") or
                   (result.get("draft") or {}).get("text") or "")
        if report["max_similarity_to_other_candidate"] >= 0.82:
            report["eligible"] = False
        scored.append((report, result))
        texts.append(text)

    eligible = [(report, result) for report, result in scored if report["eligible"]]
    if not eligible:
        raise RuntimeError(
            "NIC bounded editorial improvement found no candidate passing its "
            f"local rubric; generated={len(candidates)}, errors={len(errors)}"
        )
    selected_report, selected = max(eligible, key=lambda pair: pair[0]["score"])
    selected["editorial_iteration"] = {
        "status": "SELECTED_FROM_BOUNDED_CANDIDATES",
        "candidate_budget": budget,
        "generated_candidates": len(candidates),
        "eligible_candidates": len(eligible),
        "selected_strategy": selected_report["presentation_strategy"],
        "selected_score": selected_report["score"],
        "selection_is_reward_prediction": False,
        "reward_claim": "NOT_CLAIMED",
        "candidates": [dict(report) for report, _ in scored],
        "generation_errors": errors,
        "quality_and_publication_gates_remain_authoritative": True,
    }
    return selected
