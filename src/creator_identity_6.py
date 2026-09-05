"""Creator 6.4 identity + anti-repetition authority.

Learns from published-cycle history and the current 6.3 opportunity ranking.
It does not replace evidence or invent market facts. It only chooses among
already-ranked opportunities and adds deliberate creative-variation constraints.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics/publication_log.jsonl"
RANKING = ROOT / "data/live/opportunity_ranking_6.json"
PREF = ROOT / "data/live/editorial_preflight.json"
OUT = ROOT / "data/live/creator_identity_6.json"


def load_json(path):
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def norm(v):
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()


def family(value, kind):
    s = norm(value)
    if not s:
        return "unknown"
    if kind == "hook":
        if any(x in s for x in ("just moved", "up ", "down ", "surged", "dropped", "rallied")):
            return "price_move"
        if any(x in s for x in ("breaking", "just in", "announced", "launch", "approval", "listed")):
            return "event_news"
        if any(x in s for x in ("watch", "key level", "setup", "support", "resistance")):
            return "setup_level"
        if any(x in s for x in ("why", "because", "here s the", "the reason")):
            return "explanation"
        if any(x in s for x in ("would you", "bullish", "bearish", "choose")):
            return "question_led"
        return "statement"
    if kind == "cta":
        if any(x in s for x in ("bullish", "bearish", "wait")):
            return "stance_choice"
        if any(x in s for x in ("buy", "sell", "entry", "enter")):
            return "trade_action"
        if any(x in s for x in ("watch", "confirm", "break", "hold")):
            return "confirmation"
        if any(x in s for x in ("which", "pick", "choose")):
            return "forced_choice"
        if "why" in s or "what would" in s:
            return "reasoning"
        return "open_question"
    return s[:60]


def history():
    rows = []
    if not LOG.exists():
        return rows
    for line in LOG.read_text(encoding="utf-8").splitlines()[-80:]:
        try:
            x = json.loads(line)
            if isinstance(x, dict) and x.get("status") == "PUBLISHED_AUTONOMOUSLY":
                rows.append(x)
        except Exception:
            pass
    return rows


def candidate_symbol(c):
    raw = c.get("symbol")
    if not raw:
        symbols = c.get("symbols") or []
        raw = symbols[0] if symbols else ""
    s = str(raw or "").upper().replace("$", "").strip()
    return s[:-4] if s.endswith("USDT") else s


def main():
    ranking = load_json(RANKING)
    pref = load_json(PREF)
    rows = history()
    recent = rows[-12:]
    recent_symbols = [str(x.get("symbol") or "").upper() for x in recent if x.get("symbol")]
    recent_categories = [str(x.get("content_category") or "").lower() for x in recent]
    recent_formats = [str(x.get("format") or "").lower() for x in recent]
    recent_hooks = [family(x.get("hook"), "hook") for x in recent]
    recent_ctas = [family(x.get("discussion_question"), "cta") for x in recent]
    symbol_counts = Counter(recent_symbols)
    category_counts = Counter(recent_categories)
    hook_counts = Counter(recent_hooks)
    cta_counts = Counter(recent_ctas)

    selected = pref.get("selected_opportunity") or ranking.get("selected") or {}
    manual = bool(pref.get("manual_topic")) or bool(selected.get("manual_topic"))
    protected = str(selected.get("category") or "").lower() in {"creator_signal_outcome", "follow_up"}

    candidates = ranking.get("top_candidates") or []
    scored = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        c = dict(raw)
        base = float(c.get("ranker_score") or c.get("score") or 0)
        s = candidate_symbol(c)
        cat = str(c.get("lane") or c.get("category") or "").lower()
        novelty = 0.0
        reasons = []
        if s and symbol_counts.get(s, 0):
            penalty = min(24, 10 * symbol_counts[s])
            novelty -= penalty
            reasons.append(f"asset_repeat:-{penalty}")
        if cat and category_counts.get(cat, 0):
            penalty = min(12, 4 * category_counts[cat])
            novelty -= penalty
            reasons.append(f"category_repeat:-{penalty}")
        if recent_formats and cat in {"breaking_news", "news_and_macro", "news_market_impact"} and recent_formats[-1] == "article":
            novelty -= 4
            reasons.append("format_repeat:-4")
        if cat in {"technical_breakout", "top_mover", "volume_anomaly", "liquidation"} and recent_categories[-1:] and recent_categories[-1] == cat:
            novelty -= 8
            reasons.append("lane_repeat:-8")
        if cat in {"breaking_news", "news_market_impact"} and c.get("title"):
            novelty += 4
            reasons.append("fresh_news:+4")
        if c.get("title") and not s:
            novelty -= 40
            reasons.append("no_chart_asset:-40")
        c["identity_score"] = round(base + novelty, 2)
        c["identity_adjustments"] = reasons
        scored.append(c)

    scored.sort(key=lambda x: float(x.get("identity_score") or 0), reverse=True)
    if manual or protected:
        chosen = selected
        reason = "Manual topic or verified creator follow-up/outcome retained."
    elif scored:
        chosen = dict(scored[0])
        reason = "Creator 6.4 selected the strongest ranked opportunity after repetition and identity penalties."
        if chosen.get("title") and not candidate_symbol(chosen):
            alternatives = [x for x in scored[1:] if candidate_symbol(x)]
            if alternatives:
                chosen = dict(alternatives[0])
                reason += " No-chart news candidate skipped; selected a chartable evidence-backed alternative."
            else:
                raise SystemExit("No chartable opportunity available for TradingView-only publication policy")
        if chosen.get("title"):
            chosen.update({
                "category": "breaking_news" if float(chosen.get("score") or 0) >= 70 else "news_and_macro",
                "news_title": chosen.get("title"),
                "news_url": chosen.get("url"),
                "news_source": chosen.get("source"),
                "news_published_at": chosen.get("published_at"),
                "news_score": float(chosen.get("score") or 0),
                "symbol": candidate_symbol(chosen),
            })
        else:
            chosen["category"] = chosen.get("lane") or chosen.get("category") or "top_mover"
            chosen["symbol"] = candidate_symbol(chosen)
        chosen["reason"] = reason
        chosen["ranker_score"] = float(chosen.get("ranker_score") or chosen.get("score") or 0)

    rotation = {
        "avoid_asset": recent_symbols[:5],
        "avoid_categories": recent_categories[-3:],
        "avoid_hook_families": [x for x, _ in hook_counts.most_common(3)],
        "avoid_cta_families": [x for x, _ in cta_counts.most_common(3)],
        "avoid_formats": recent_formats[-2:],
        "preferred_next_hook_families": ["event_news", "setup_level", "explanation", "question_led", "statement"],
        "preferred_cta_families": ["stance_choice", "confirmation", "forced_choice", "reasoning", "trade_action"],
        "rules": [
            "Do not reuse the previous post's opening structure.",
            "Do not reuse the previous post's CTA family unless the story genuinely requires it.",
            "Do not lead with the same asset and percentage-move template repeatedly.",
            "Keep one clear idea per post and make the selected story the center of gravity.",
            "Use TradingView evidence only when it matches the selected asset/story.",
            "Never invent an asset merely to obtain a chart.",
            "A fresh material breaking-news event may override repetition penalties.",
        ],
    }
    identity_instruction = (
        "Creator 6.4 identity rotation: avoid recent asset, hook, structure and CTA repetition. "
        "Do not open with the same ticker-plus-percentage template. Use a materially different narrative rhythm. "
        "Pick exactly one specific, low-friction interaction question. Preserve evidence and selected-story authority. "
        "TradingView must be the only chart source and must match the selected asset; never use BTC as an arbitrary proxy."
    )
    chosen["instruction"] = identity_instruction
    chosen["identity_rotation"] = rotation
    pref["selected_opportunity"] = chosen
    pref["creator_identity_6"] = {
        "version": "6.4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_reason": reason,
        "rotation": rotation,
        "recent_history_count": len(rows),
        "recent_symbols": recent_symbols,
        "recent_categories": recent_categories,
        "recent_formats": recent_formats,
        "recent_hook_families": recent_hooks,
        "recent_cta_families": recent_ctas,
    }
    pref["content_director_instruction"] = identity_instruction
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "version": "6.4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected": chosen,
        "rotation": rotation,
        "top_candidates": scored[:20],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    PREF.write_text(json.dumps(pref, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "version": "6.4",
        "selected_category": chosen.get("category"),
        "selected_symbol": chosen.get("symbol"),
        "selected_news": chosen.get("news_title"),
        "recent_posts": len(rows),
        "repetition_assets": recent_symbols[:5],
        "rotation_active": True,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
