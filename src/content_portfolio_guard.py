"""Content Portfolio Manager: stop repetitive single-asset publishing.

This stage operates after opportunity ranking and before the authoritative
opportunity is frozen. It chooses among already-researched candidates while
optimizing for story diversity, asset diversity, thesis freshness and reader
value. It never invents a new asset or signal.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data/live/editorial_preflight.json"
DIRECTOR = ROOT / "data/live/content_director_brief.json"
LOG = ROOT / "analytics/publication_log.jsonl"
OUT = ROOT / "data/live/content_portfolio_guard.json"

MIN_SCORE = float(os.getenv("PORTFOLIO_MIN_SCORE", "68"))
RECENT_WINDOW = int(os.getenv("PORTFOLIO_RECENT_WINDOW", "12"))
BTC_MAX_RECENT = int(os.getenv("PORTFOLIO_BTC_MAX_RECENT", "1"))
ASSET_MAX_RECENT = int(os.getenv("PORTFOLIO_ASSET_MAX_RECENT", "2"))
SIMILARITY_BLOCK = float(os.getenv("PORTFOLIO_SIMILARITY_BLOCK", "0.58"))

PRIMARY = {
    "creator_signal_outcome", "capital_flow_long", "capital_flow_short", "follow_up",
    "technical_setup", "top_gainers", "top_losers", "high_volatility", "volume_leaders",
}
NON_SIGNAL = {"breaking_news", "news_and_macro", "watchlist", "comparison", "education", "crypto_meme"}
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "from",
    "as", "is", "are", "this", "that", "it", "its", "at", "by", "be", "has", "have",
    "will", "can", "now", "why", "what", "how", "than", "into", "after", "over", "under",
    "market", "crypto", "price", "today", "latest", "update", "binance",
}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def symbol(value) -> str:
    text = str(value or "").upper().replace("BINANCE:", "").replace("$", "").strip()
    return text[:-4] if text.endswith("USDT") else text


def category(item: dict) -> str:
    return str(item.get("category") or item.get("lane") or item.get("content_category") or item.get("type") or "").lower()


def lane_priority(cat: str) -> int:
    if cat in PRIMARY:
        return 2
    if cat in NON_SIGNAL:
        return 1 if cat != "crypto_meme" else 0
    return 1


def words(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]{3,}", str(text or "").lower())
    return {x for x in raw if x not in STOPWORDS}


def similarity(left: str, right: str) -> float:
    a, b = words(left), words(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def text_of(item: dict) -> str:
    parts = [item.get("topic"), item.get("title"), item.get("news_title"), item.get("hook"), item.get("reason"), item.get("editorial_style")]
    setup = item.get("trade_setup") or {}
    parts.extend([setup.get("side"), str(setup.get("trigger")), str(setup.get("invalidation"))])
    return " ".join(str(x or "") for x in parts if x)


def recent_publications() -> list[dict]:
    if not LOG.exists():
        return []
    rows: list[dict] = []
    for line in LOG.read_text(encoding="utf-8").splitlines()[-160:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("status") == "PUBLISHED_AUTONOMOUSLY":
            rows.append(row)
    return rows[-RECENT_WINDOW:]


def asset_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for raw in (row.get("symbol"), row.get("selected_lane_symbol")):
            s = symbol(raw)
            if s:
                counts[s] = counts.get(s, 0) + 1
                break
    return counts


def recent_same_category(rows: list[dict], cat: str) -> int:
    return sum(1 for r in rows[-5:] if category(r) == cat)


def is_material_followup(candidate: dict) -> bool:
    cat = category(candidate)
    return cat in {"creator_signal_outcome", "follow_up"} and bool(
        candidate.get("proof_status") or candidate.get("outcome") or candidate.get("outcome_status")
        or candidate.get("new_evidence") or candidate.get("next_hook")
    )


def news_asset_evidence(candidate: dict) -> bool:
    cat = category(candidate)
    if cat not in {"breaking_news", "news_and_macro", "news_market_impact", "news"}:
        return True
    title = str(candidate.get("title") or candidate.get("news_title") or "").lower()
    summary = str(candidate.get("summary") or "").lower()
    s = symbol(candidate.get("symbol")).lower()
    if not s:
        return False
    aliases = {
        "btc": ["bitcoin", "$btc", "btc"], "eth": ["ethereum", "$eth", "eth", "ether"],
        "bnb": ["bnb", "binance coin"], "sol": ["solana", "$sol", "sol"],
        "xrp": ["xrp", "ripple"], "doge": ["dogecoin", "$doge", "doge"],
    }
    names = aliases.get(s, [f"${s}", s])
    return any(re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", title + " " + summary) for name in names)


def candidate_key(item: dict) -> str:
    return f"{symbol(item.get('symbol'))}|{category(item)}|{str(item.get('type') or '').lower()}"


def main() -> int:
    pre = load(PREFLIGHT)
    brief = load(DIRECTOR)
    ranked = brief.get("ranked_stories") or []
    current = pre.get("selected_opportunity") or {}
    current = current if isinstance(current, dict) else {}
    recent = recent_publications()
    counts = asset_counts(recent)
    recent_texts = [text_of(r) for r in recent[-8:]]
    ranked = [x for x in ranked if isinstance(x, dict) and symbol(x.get("symbol"))]

    evaluated = []
    seen = set()
    for raw in ranked:
        s = symbol(raw.get("symbol"))
        cat = category(raw)
        key = candidate_key(raw)
        if key in seen:
            continue
        seen.add(key)
        score = num(raw.get("ranker_score") or raw.get("score"))
        if score < MIN_SCORE:
            continue

        reasons = []
        hard_block = False
        count = counts.get(s, 0)
        material_followup = is_material_followup(raw)
        priority = lane_priority(cat)

        if not news_asset_evidence(raw):
            hard_block = True
            reasons.append("news_asset_not_explicitly_supported")

        if s == "BTC" and count >= BTC_MAX_RECENT and not material_followup:
            hard_block = True
            reasons.append(f"btc_overexposed_{count}_recent_posts")
        elif count >= ASSET_MAX_RECENT and not material_followup:
            hard_block = True
            reasons.append(f"asset_overexposed_{count}_recent_posts")

        same_cat = recent_same_category(recent, cat)
        if same_cat >= 2 and cat not in {"creator_signal_outcome", "follow_up"}:
            score -= 6
            reasons.append("category_repeat_penalty")

        candidate_text = text_of(raw)
        max_sim = max((similarity(candidate_text, t) for t in recent_texts), default=0.0)
        if max_sim >= SIMILARITY_BLOCK and not material_followup:
            hard_block = True
            reasons.append(f"semantic_similarity_{max_sim:.2f}")

        if count == 0:
            score += 7
            reasons.append("new_asset_bonus")
        if priority == 2:
            score += 8
            reasons.append("primary_signal_lane_bonus")
        if cat in {"capital_flow_long", "capital_flow_short"} and num(raw.get("flow_confidence")) >= 70:
            score += 5
            reasons.append("high_flow_confidence_bonus")

        evaluated.append({
            "candidate": raw,
            "score_before_guard": round(num(raw.get("ranker_score") or raw.get("score")), 2),
            "portfolio_score": round(score, 2),
            "lane_priority": priority,
            "asset_recent_count": count,
            "recent_same_category": same_cat,
            "max_recent_semantic_similarity": round(max_sim, 3),
            "hard_block": hard_block,
            "reasons": reasons,
        })

    allowed = [x for x in evaluated if not x["hard_block"]]
    # Signal-first still wins: among non-blocked candidates, lane priority is
    # considered before score, so a qualified signal is not displaced by a
    # generic news item merely because the latter has a slightly higher score.
    evaluated.sort(key=lambda x: (not x["hard_block"], x["lane_priority"], x["portfolio_score"]), reverse=True)
    allowed.sort(key=lambda x: (x["lane_priority"], x["portfolio_score"]), reverse=True)
    chosen_entry = allowed[0] if allowed else None
    chosen = chosen_entry["candidate"] if chosen_entry else None

    if current and category(current) in {"creator_signal_outcome", "follow_up"} and is_material_followup(current):
        chosen = current
        decision = "PROTECTED_OUTCOME_OR_FOLLOWUP"
        reason = "material_outcome_update_is_allowed_to_revisit_a_recent_asset"
        chosen_entry = None
    elif chosen:
        decision = "DIVERSIFIED_STORY_SELECTED"
        reason = "portfolio_manager_selected_the_best_non_repetitive_candidate"
    else:
        decision = "WAIT_FOR_DIFFERENT_STORY"
        reason = "all_qualified_candidates_are_repetitive_or_unsupported"

    publish = chosen is not None
    if publish:
        chosen = dict(chosen)
        chosen["portfolio_guard_selected"] = True
        chosen["portfolio_score"] = round(chosen_entry["portfolio_score"], 2) if chosen_entry else num(chosen.get("score"))
        chosen["symbol"] = symbol(chosen.get("symbol")) + "USDT"
        pre["selected_opportunity"] = chosen
        pre["content_portfolio_guard"] = {
            "decision": decision, "reason": reason, "selected_symbol": symbol(chosen.get("symbol")),
            "selected_category": category(chosen), "recent_asset_counts": counts, "recent_window": len(recent),
        }
        brief["authoritative_selection"] = chosen
        brief["portfolio_guard"] = pre["content_portfolio_guard"]
        DIRECTOR.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
        PREFLIGHT.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        pre["selected_opportunity"] = {}
        pre["content_portfolio_guard"] = {
            "decision": decision, "reason": reason, "recent_asset_counts": counts, "recent_window": len(recent),
        }
        PREFLIGHT.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.1-content-portfolio",
        "publish": publish,
        "decision": decision,
        "reason": reason,
        "selected": chosen,
        "recent_asset_counts": counts,
        "recent_window": len(recent),
        "candidates_considered": len(evaluated),
        "blocked_candidates": [x for x in evaluated if x["hard_block"]][:12],
        "top_allowed_candidates": allowed[:12],
        "policy": {
            "btc_max_recent_posts": BTC_MAX_RECENT,
            "asset_max_recent_posts": ASSET_MAX_RECENT,
            "recent_window": RECENT_WINDOW,
            "semantic_similarity_block": SIMILARITY_BLOCK,
            "generic_news_cannot_create_btc_fallback": True,
            "signal_lane_priority_over_generic_news": True,
            "wait_when_repetitive": True,
            "outcome_followups_can_revisit_asset": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
