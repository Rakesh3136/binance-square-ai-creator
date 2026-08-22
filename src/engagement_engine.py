"""Cheap, deterministic growth layer before Gemini.

The engine does not invent facts or market data. It chooses among already-scanned
opportunities using novelty, lane diversity and interaction potential, then tells
the AI which human-style format to use.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PREFLIGHT = Path("data/live/editorial_preflight.json")
PUBLICATIONS = Path("analytics/publication_log.jsonl")
OUTPUT = Path("data/live/engagement_strategy.json")

FORMAT_ROTATION = [
    "BREAKING FLASH",
    "QUICK MARKET TAKE",
    "CHART BREAKDOWN",
    "DATA SNAPSHOT",
    "NEWS REACTION",
    "CONTRARIAN QUESTION",
    "COIN VS COIN",
    "ONE CHART ONE QUESTION",
]

INTERACTIVE_CATEGORIES = {
    "top_gainers": 12,
    "top_losers": 12,
    "volume_leaders": 14,
    "new_listings": 16,
    "high_volatility": 10,
    "BTC_ETH_market_context": 6,
    "news_and_macro": 18,
}


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def recent_publications(hours: int = 36):
    rows = []
    if not PUBLICATIONS.exists():
        return rows
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            dt = datetime.fromisoformat(str(row.get("published_at", "")).replace("Z", "+00:00"))
            if dt >= cutoff:
                rows.append(row)
        except Exception:
            continue
    return rows


def base_symbol(value: str) -> str:
    value = str(value or "").upper().strip()
    return value[:-4] if value.endswith("USDT") else value


def main():
    preflight = load(PREFLIGHT, {})
    candidates = preflight.get("candidate_pool") or []
    publications = recent_publications()

    recent_assets = Counter()
    recent_categories = Counter()
    recent_formats = Counter()
    for row in publications:
        symbol = base_symbol(row.get("selected_lane_symbol") or row.get("symbol") or "")
        if symbol:
            recent_assets[symbol] += 1
        category = str(row.get("content_category") or "").lower()
        if category:
            recent_categories[category] += 1
        style = str(row.get("editorial_style") or "").upper()
        if style:
            recent_formats[style] += 1

    # Score the top scanned opportunities. A huge raw score cannot overwhelm
    # repetition: we want a newsroom, not a single-coin feed.
    ranked = []
    for candidate in candidates:
        symbol = base_symbol(candidate.get("topic") or candidate.get("symbol") or "")
        category = str(candidate.get("category") or "").lower()
        raw = float(candidate.get("adjusted_score") or candidate.get("raw_score") or 0)
        asset_penalty = min(70, recent_assets.get(symbol, 0) * 28) if symbol else 0
        category_penalty = min(28, recent_categories.get(category, 0) * 8)
        interaction_bonus = INTERACTIVE_CATEGORIES.get(category, 8)
        novelty_bonus = 16 if recent_assets.get(symbol, 0) == 0 else 0
        score = raw - asset_penalty - category_penalty + interaction_bonus + novelty_bonus
        ranked.append({**candidate, "engagement_score": round(score, 2), "asset_penalty": asset_penalty, "category_penalty": category_penalty, "interaction_bonus": interaction_bonus})

    ranked.sort(key=lambda x: x["engagement_score"], reverse=True)
    selected = ranked[0] if ranked else (preflight.get("best_market_candidate") or {})

    # Rotate formats deterministically; do not repeat the same style several times.
    used_styles = {style for style, count in recent_formats.items() if count >= 1}
    preferred_style = next((style for style in FORMAT_ROTATION if style not in used_styles), FORMAT_ROTATION[len(publications) % len(FORMAT_ROTATION)])

    # Every selected story gets an interaction blueprint. Gemini must still
    # decide whether the evidence supports the angle.
    category = str(selected.get("category") or "news_and_macro").lower()
    interaction = {
        "primary_goal": "earn a genuine comment or click, not a vanity metric",
        "question_shape": "A/B choice, prediction check, or one specific technical observation",
        "avoid": ["generic What do you think?", "follow/like begging", "fake urgency", "guaranteed returns", "long essay"],
        "monetization": "Include a relevant $cashtag and/or real chart widget when the post discusses a tradeable asset so eligible reader activity can be attributed.",
        "format": preferred_style,
        "category": category,
    }

    selected = dict(selected)
    selected["instruction"] = (
        f"Use {category.replace('_', ' ')} as the lane. This is an engagement-first selection, not merely the highest raw score. "
        f"Preferred human format: {preferred_style}. Build a short scroll-stopping hook, one useful insight, and one easy-to-answer question. "
        "If the selected asset has been covered recently, switch to another candidate unless there is a genuinely major verified event."
    )
    selected["engagement_strategy"] = interaction

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected": selected,
        "ranked_candidates": ranked[:12],
        "recent_assets": dict(recent_assets),
        "recent_categories": dict(recent_categories),
        "recent_formats": dict(recent_formats),
        "format_rotation": FORMAT_ROTATION,
        "interaction_blueprint": interaction,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Feed the selected strategy back into preflight for the AI prompt.
    preflight["selected_opportunity"] = selected
    preflight["engagement_strategy"] = interaction
    preflight["engagement_ranked_candidates"] = ranked[:12]
    PREFLIGHT.write_text(json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
