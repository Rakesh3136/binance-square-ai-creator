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


def sentence_redundancy(sentences: list[str]) -> float:
    """Return the highest content-word overlap between distinct sentences."""
    stop = {
        "the", "a", "an", "and", "or", "but", "if", "then", "is", "are",
        "was", "were", "be", "to", "of", "in", "on", "at", "for", "with",
        "as", "this", "that", "it", "its", "we", "you", "your", "what",
        "would", "could", "should", "next", "still", "around", "because",
        "whether", "about", "from", "than", "have", "has", "had",
    }
    token_sets = []
    for sentence in sentences:
        words = set(re.findall(r"[a-z0-9$]+", sentence.lower())) - stop
        if words:
            token_sets.append(words)
    highest = 0.0
    for i, left in enumerate(token_sets):
        for right in token_sets[i + 1:]:
            union = left | right
            if union:
                highest = max(highest, len(left & right) / len(union))
    return round(highest, 4)


def score_candidate(result: dict[str, Any], context: dict[str, Any],
                    previous_texts: list[str] | None = None) -> dict[str, Any]:
    draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
    post = str(draft.get("post") or draft.get("text") or "").strip()
    symbol = str(draft.get("symbol") or "").upper().replace("USDT", "").strip()
    normalized = _normalize(post)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", post) if s.strip()]
    questions = post.count("?")
    redundancy = sentence_redundancy(sentences)
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
    if redundancy >= 0.55:
        issues.append("repeats_same_point_across_sentences")

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
    return {
        "score": round(score, 2),
        "eligible": not issues,
        "issues": issues,
        "character_count": len(post),
        "sentence_count": len(sentences),
        "sentence_redundancy": redundancy,
        "question_count": questions,
        "max_similarity_to_other_candidate": round(max_similarity, 4),
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
    for result in candidates:
        report = score_candidate(result, context, texts)
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
