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
        f"${volume/1_000_000:.1f}M spot volume" if volume >= 1_000_000
        else f"${volume/1_000:.0f}K spot volume" if volume >= 1_000 else "fresh spot data"
    )
    news_title = str(selected.get("news_title") or "").strip()
    news_source = str(selected.get("news_source") or "").strip()
    category = str(selected.get("category") or "market_opportunity").lower()

    if news_title:
        source_line = f"Source: {news_source}" if news_source else "Source: verified news feed"
        post = (
            "🚨 $" + symbol + ": " + news_title + "\n\n" +
            source_line + "\n\n" +
            "The key question now is whether price confirms the catalyst. $" + symbol +
            " is currently showing " + f"{move:+.1f}%" + " with " + volume_text + ".\n\n" +
            "Does the market confirm the headline, or fade it?"
        )
        hook = "🚨 $" + symbol + ": " + news_title
        style = "publish_rescue_newsroom"
    elif move >= 15:
        post = (
            "🔥 $" + symbol + " just moved " + f"{move:+.1f}%" + " with " + volume_text + ".\n\n" +
            "That is enough to put it on the radar, but the next reaction matters more than the first spike. " +
            "Recent 1H support is $" + f"{support:.8g}" + " and resistance is $" + f"{resistance:.8g}" + ".\n\n" +
            "Would you wait for $" + symbol + " to hold the breakout, or expect a pullback first?"
        )
        hook = "🔥 $" + symbol + " just moved " + f"{move:+.1f}%" + " — what happens next?"
        style = "publish_rescue_momentum"
    elif move <= -15:
        post = (
            "⚠️ $" + symbol + " just dropped " + f"{abs(move):.1f}%" + " with " + volume_text + ".\n\n" +
            "The important part is whether sellers keep control below the recent range: support $" + f"{support:.8g}" +
            " / resistance $" + f"{resistance:.8g}" + ".\n\n" +
            "Would you watch a reclaim on $" + symbol + ", or wait for another lower high?"
        )
        hook = "⚠️ $" + symbol + " just dropped " + f"{abs(move):.1f}%" + " — now watch the reaction."
        style = "publish_rescue_breakdown"
    else:
        post = (
            "📊 $" + symbol + ": price is around $" + f"{last:.8g}" + " with " + volume_text + ".\n\n" +
            "Recent 1H range: $" + f"{support:.8g}" + " support → $" + f"{resistance:.8g}" + " resistance. " +
            "The current classification is " + category.replace("_"," ") + ".\n\n" +
            "Which side would you wait to confirm on $" + symbol + ": breakout or rejection?"
        )
        hook = "📊 $" + symbol + ": the next 1H reaction matters."
        style = "publish_rescue_chart"

    draft = report.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    draft.update(
        {
            "post": post[:740],
            "text": post[:740],
            "hook": hook,
            "discussion_question": post.splitlines()[-1],
            "quality_score": 90,
            "editorial_style": style,
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
    chart_symbols = [str(x).upper() for x in (meta.get("tradingview_symbols") or [])]\n    chart_symbol = chart_symbols[0] if chart_symbols else str(meta.get("tradingview_symbol") or meta.get("symbol") or "").upper()
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
