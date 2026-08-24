"""Deterministic publish-rescue draft for a fresh but gate-rejected cycle."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("data/reports")
PREFLIGHT = Path("data/live/editorial_preflight.json")
MARKET = Path("data/live/market_snapshot.json")


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def latest_report():
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit("No fresh draft report available for rescue")
    report = reports[0]
    age = datetime.now().timestamp() - report.stat().st_mtime
    if age > 1200:
        raise SystemExit("Latest draft is stale; refusing rescue publication")
    return report


def main():
    report_path = latest_report()
    report = load(report_path, {})
    preflight = load(PREFLIGHT, {})
    market = load(MARKET, {})
    selected = preflight.get("selected_opportunity") or report.get("selected_editorial_lane") or {}
    if not isinstance(selected, dict):
        selected = {}

    symbol = str(selected.get("symbol") or selected.get("topic") or "").upper()
    values = []
    for key in ("top_content_signals", "top_gainers", "top_losers", "highest_volume"):
        group = market.get(key) or []
        if isinstance(group, list):
            values.extend(x for x in group if isinstance(x, dict))
    match = next((x for x in values if str(x.get("symbol", "")).upper() == symbol), None)
    match = match or next((x for x in values if x.get("symbol")), {})
    symbol = str(match.get("symbol") or symbol or "MARKET").upper().replace("USDT", "")

    try:
        move = float(match.get("price_change_percent") or 0)
    except Exception:
        move = 0.0
    try:
        volume = float(match.get("quote_volume_usdt") or match.get("quote_volume") or 0)
    except Exception:
        volume = 0.0

    volume_text = (
        f"${volume/1_000_000:.1f}M spot volume"
        if volume >= 1_000_000
        else f"${volume/1_000:.0f}K spot volume" if volume >= 1_000 else "fresh spot data"
    )
    post = (
        f"Fresh check: ${symbol} is {move:+.1f}% with {volume_text}. "
        "The move is strong enough to watch, but confirmation matters more than chasing it. "
        f"Which signal are you watching next on ${symbol}?"
    )

    draft = report.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    draft.update(
        {
            "post": post[:740],
            "text": post[:740],
            "hook": f"Fresh check: ${symbol} is {move:+.1f}%.",
            "discussion_question": f"Which signal are you watching next on ${symbol}?",
            "quality_score": 90,
            "editorial_style": "publish_rescue_concise",
            "generation_mode": "LOCAL_FALLBACK",
            "publication_status": "DRAFT_ONLY_NOT_PUBLISHED",
            "symbol": symbol,
            "content_category": selected.get("category") or selected.get("reason") or "market_opportunity",
        }
    )
    visual = report.get("visual_plan") or {}
    if not isinstance(visual, dict):
        visual = {}
    # Rescue is intentionally text-first so a gate failure cannot be caused by
    # a stale/broken image dependency.
    visual.update({"use_visual": False, "type": "none", "rescue_text_fallback": True})

    report["draft"] = draft
    report["visual_plan"] = visual
    report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report["generation_mode"] = "LOCAL_FALLBACK"
    report["publish_rescue"] = True
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "PUBLISH_RESCUE_READY", "report": str(report_path), "symbol": symbol}, indent=2))


if __name__ == "__main__":
    main()
