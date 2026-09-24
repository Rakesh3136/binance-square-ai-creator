"""Deterministic visual decision for the final publication draft.

The decision is derived from the final draft/context only. It never creates
market data or chart levels.
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
NO_VISUAL_LANES = {
    "education", "commentary", "community", "text_only",
    "crypto_meme", "market_meme", "trader_humor", "result_followup",
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
    decision = {
        "version": "1.0-deterministic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "draft_path": str(draft_path),
        "need_visual": need_visual,
        "provider": "TradingView" if need_visual else None,
        "type": "candlestick_chart" if need_visual else "none",
        "symbol": symbol or None,
        "timeframe": str((data.get("visual_plan") or {}).get("timeframe") or "1H") if need_visual else None,
        "reason": (
            "draft explicitly requests a visual or is a market/setup lane"
            if need_visual else
            "lane is allowed to publish without a visual"
        ),
        "rules": [
            "Use real market data only.",
            "Never invent chart levels.",
            "Visual is evidence, not a guarantee.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
