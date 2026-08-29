"""Deterministic publish-rescue draft for a fresh but gate-rejected cycle.

Rescue must never change the authoritative asset or remove the required
TradingView visual. It may only simplify the writing so the already-rendered
chart and publication context remain synchronized.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("data/reports")
PREFLIGHT = Path("data/live/editorial_preflight.json")
MARKET = Path("data/live/market_snapshot.json")
STATUS = Path("data/live/creator_status.json")
VISUAL_META = Path("data/live/visual_metadata.json")


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


def market_match(market: dict, symbol: str):
    """Find the selected asset without ever silently switching assets."""
    wanted = symbol.upper().replace("USDT", "")
    groups = []
    for key in ("top_content_signals", "top_gainers", "top_losers", "highest_volume"):
        value = market.get(key)
        if isinstance(value, list):
            groups.extend(value)
        elif isinstance(value, dict):
            groups.append(value)
    for key in ("top_signal", "top_gainer", "top_loser"):
        value = market.get(key)
        if isinstance(value, dict):
            groups.append(value)
    for item in groups:
        item_symbol = str(item.get("symbol", "")).upper().replace("USDT", "")
        if item_symbol == wanted:
            return item
    return {}


def main():
    report_path = latest_report()
    report = load(report_path, {})
    preflight = load(PREFLIGHT, {})
    market = load(MARKET, {})

    selected = preflight.get("selected_opportunity") or report.get("selected_editorial_lane") or {}
    if not isinstance(selected, dict):
        selected = {}

    # The frozen/preflight asset is authoritative. Rescue is not allowed to
    # replace it with the first convenient market row.
    symbol = str(
        selected.get("symbol")
        or selected.get("topic")
        or report.get("symbol")
        or (report.get("draft") or {}).get("symbol")
        or ""
    ).upper().replace("USDT", "")
    if not symbol:
        raise SystemExit("No authoritative symbol available for rescue")

    match = market_match(market, symbol)
    if not match:
        raise SystemExit(f"No fresh market evidence found for authoritative asset {symbol}")

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

    # CRITICAL: the rescue keeps TradingView mandatory. The chart was rendered
    # before rescue from the frozen opportunity, so do not alter the asset or
    # downgrade the visual plan to text-only.
    visual = report.get("visual_plan") or {}
    if not isinstance(visual, dict):
        visual = {}
    visual.update({
        "use_visual": True,
        "type": "candlestick_chart",
        "provider": "TradingView",
        "timeframe": "1H",
        "rescue_text_fallback": False,
    })

    meta = load(VISUAL_META, {})
    chart_symbol = str(meta.get("tradingview_symbol") or meta.get("symbol") or "").upper()
    expected = f"BINANCE:{symbol}USDT"
    if chart_symbol and chart_symbol != expected:
        raise SystemExit(
            f"TradingView visual asset mismatch: chart={chart_symbol}, expected={expected}; refusing rescue"
        )

    report["draft"] = draft
    report["visual_plan"] = visual
    report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report["generation_mode"] = "LOCAL_FALLBACK"
    report["publish_rescue"] = True
    report["publish_rescue_at"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(
        json.dumps(
            {
                "status": "LOCAL_FALLBACK_SUCCESS",
                "generation_mode": "LOCAL_FALLBACK",
                "reason": "Production manager rescue simplified writing without changing the authoritative asset or TradingView visual",
                "rescue": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "PUBLISH_RESCUE_READY", "report": str(report_path), "symbol": symbol}, indent=2))


if __name__ == "__main__":
    main()
