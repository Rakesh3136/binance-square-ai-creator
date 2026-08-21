"""Deterministic editorial guardrails used before expensive AI generation.

This module is intentionally dependency-free. It does not decide what is true;
it only filters obvious repetition/filler and provides a compact decision context
for the higher-level AI editor.
"""
from __future__ import annotations

import re
from collections import Counter


def normalize_topic(text: str) -> str:
    text = (text or "").upper()
    symbols = re.findall(r"\$?[A-Z0-9]{2,12}(?:USDT)?", text)
    for symbol in symbols:
        clean = symbol.replace("$", "")
        if clean.endswith("USDT"):
            clean = clean[:-4]
        if clean in {"BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "DOGE", "TRX", "LINK", "AVAX", "DOT", "LTC", "SHIB", "SUI", "TON"}:
            return clean
    return ""


def repetition_penalty(topic: str, recent_posts: list[dict], window: int = 6) -> int:
    """Return a bounded penalty (0-40) for repeated recent asset/topic coverage."""
    target = normalize_topic(topic)
    if not target:
        return 0
    recent = recent_posts[-window:]
    count = 0
    for post in recent:
        value = normalize_topic(str(post.get("topic", "")))
        if value == target:
            count += 1
    return min(40, count * 10)


def should_spend_ai_request(candidate_score: float, topic: str, recent_posts: list[dict],
                            minimum_score: float = 70) -> tuple[bool, int]:
    """Cheap gate: don't spend a scarce Gemini request on weak/repetitive stories."""
    penalty = repetition_penalty(topic, recent_posts)
    adjusted = max(0, int(candidate_score) - penalty)
    return adjusted >= minimum_score, penalty


def summarize_recent_topics(recent_posts: list[dict], window: int = 8) -> dict:
    topics = []
    for post in recent_posts[-window:]:
        topic = normalize_topic(str(post.get("topic", "")))
        if topic:
            topics.append(topic)
    return {
        "recent_topics": topics,
        "topic_counts": dict(Counter(topics)),
        "repetition_rule": "Repeated topics must lose priority unless there is a genuinely major verified breaking event."
    }
