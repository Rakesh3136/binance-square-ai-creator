"""Deterministic visual decision for the final publication draft.

Selects a differentiated chart treatment from the evidence available in the
final draft. It never creates market data or chart levels.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
CONTEXT = LIVE / "publication_context.json"
OUT = LIVE / "visual_decision.json"
PREVIOUS = LIVE / "visual_metadata.json"
NO_VISUAL_LANES = {
    "education", "commentary", "community", "text_only",
    "crypto_meme", "market_meme", "trader_humor", "result_followup",
}

# Deliberately rotate visual language so consecutive posts do not look like the
# same template. The renderer still uses real TradingView data for every chart.
CHART_PROFILES = [
    {"name": "candles_volume", "style": "1", "timeframe": "60", "label": "Candles + volume"},
    {"name": "heikin_ashi", "style": "3", "timeframe": "60", "label": "Heikin Ashi + volume"},
    {"name": "clean_structure", "style": "1", "timeframe": "240", "label": "4H structure"},
    {"name": "higher_timeframe", "style": "1", "timeframe": "D", "label": "Daily structure"},
    {"name": "line_context", "style": "4", "timeframe": "240", "label": "4H trend context"},
]

CATEGORY_PROFILE = {
    "technical_setup": [0, 1, 2],
    "capital_flow_long": [0, 2, 3],
    "capital_flow_short": [0, 2, 3],
    "news_and_macro": [2, 3, 4],
    "breaking_news": [0, 2, 4],
    "top_gainers": [0, 1, 2],
    "top_losers": [0, 1, 4],
    "high_volatility": [0, 1, 2],
    "volume_leaders": [0, 2, 4],
    "research_insight": [2, 3, 4],
    "data_surprise": [0, 2, 4],
    "market_mechanism": [2, 3, 4],
    "comparison": [0, 2, 3],
}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def clean_symbol(v: object) -> str:
    s = re.sub(r"USDT$", "", str(v or "").upper().replace("$", "").strip())
    return s if re.fullmatch(r"[A-Z0-9]{1,15}", s) else ""


def choose_profile(category: str) -> dict:
    previous = load(PREVIOUS)
    previous_profile = str(previous.get("chart_profile") or "")
    candidates = [CHART_PROFILES[i] for i in CATEGORY_PROFILE.get(category, range(len(CHART_PROFILES)))]
    for profile in candidates:
        if profile["name"] != previous_profile:
            return profile
    return candidates[0]


def main() -> int:
    import os

    draft_path = Path(os.environ.get("DRAFT_PATH", "").strip())
    if not draft_path.exists():
        print("ERROR: DRAFT_PATH is required for visual decision")
        return 2

    data = load(draft_path)
    draft = data.get("draft") if isinstance(data.get("draft"), dict) else {}
    context = load(CONTEXT)
    category = str(
        context.get("category")
        or data.get("selected_editorial_lane", {}).get("category")
        or draft.get("content_category")
        or ""
    ).lower().strip()
    symbol = clean_symbol(
        context.get("symbol")
        or data.get("selected_editorial_lane", {}).get("symbol")
        or draft.get("symbol")
    )
    requested = bool(
        draft.get("visual_requested")
        or draft.get("visual_type")
        or (data.get("visual_plan") or {}).get("required")
        or (data.get("visual_plan") or {}).get("use_visual")
    )
    setup_lane = category not in NO_VISUAL_LANES
    need_visual = bool(requested or setup_lane)
    profile = choose_profile(category) if need_visual else {"name": "none", "style": None, "timeframe": None, "label": "No visual"}
    decision = {
        "version": "2.0-differentiated-visual-routing",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "draft_path": str(draft_path),
        "need_visual": need_visual,
        "provider": "TradingView" if need_visual else None,
        "type": "tradingview_chart" if need_visual else "none",
        "chart_profile": profile["name"],
        "chart_label": profile["label"],
        "tradingview_style": profile["style"],
        "symbol": symbol or None,
        "timeframe": profile["timeframe"],
        "layout": "pair" if category == "comparison" else "single",
        "reason": (
            "draft explicitly requests a visual or is a market/setup lane; profile rotated from the previous visual"
            if need_visual else
            "lane is allowed to publish without a visual"
        ),
        "rules": [
            "Use real market data only.",
            "Never invent chart levels.",
            "Visual is evidence, not a guarantee.",
            "Avoid repeating the immediately previous chart treatment when another valid treatment exists.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
