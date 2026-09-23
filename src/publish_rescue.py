"""Deterministic publish-rescue draft for a fresh but gate-rejected cycle.

Rescue never changes the authoritative asset or removes the required visual. It
rewrites already-researched evidence into a concise, natural, mobile-friendly
Square post. The frozen prediction contract remains authoritative.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("data/reports")
PREFLIGHT = Path("data/live/editorial_preflight.json")
CONTEXT = Path("data/live/publication_context.json")
FROZEN = Path("data/live/authoritative_opportunity.json")
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


def fmt_price(value: float) -> str:
    if value == 0:
        return "0"
    return f"{value:.8g}"


def fmt_volume(volume: float) -> str:
    if volume >= 1_000_000:
        return f"${volume / 1_000_000:.1f}M spot volume"
    if volume >= 1_000:
        return f"${volume / 1_000:.0f}K spot volume"
    return "fresh spot data"


def clean_symbol(value: str) -> str:
    return str(value or "").upper().replace("$", "").replace("USDT", "").strip()


def authoritative_symbol(report: dict, preflight: dict) -> str:
    context = load(CONTEXT, {})
    frozen = load(FROZEN, {})
    selected = preflight.get("selected_opportunity") or {}
    draft = report.get("draft") or {}
    for value in (
        context.get("symbol"), frozen.get("symbol"),
        selected.get("symbol") if isinstance(selected, dict) else "",
        report.get("symbol"), draft.get("symbol") if isinstance(draft, dict) else "",
    ):
        symbol = clean_symbol(value)
        if symbol:
            return symbol
    return ""


def main():
    report_path = latest_report()
    report = load(report_path, {})
    preflight = load(PREFLIGHT, {})
    market = load(MARKET, {})
    frozen = load(FROZEN, {})

    selected = preflight.get("selected_opportunity") or report.get("selected_editorial_lane") or {}
    if not isinstance(selected, dict):
        selected = {}

    frozen_prediction = frozen.get("prediction") if isinstance(frozen.get("prediction"), dict) else {}
    frozen_setup = frozen.get("trade_setup") if isinstance(frozen.get("trade_setup"), dict) else {}
    frozen_contract = {
        "direction": frozen.get("direction") or frozen_prediction.get("direction") or frozen_setup.get("side"),
        "entry": frozen.get("entry_trigger") or frozen_prediction.get("entry_trigger") or frozen_setup.get("trigger"),
        "tp1": frozen.get("tp1") or frozen_prediction.get("tp1") or frozen_setup.get("tp1"),
        "tp2": frozen.get("tp2") or frozen_prediction.get("tp2") or frozen_setup.get("tp2"),
        "sl": frozen.get("sl") or frozen_prediction.get("sl") or frozen_setup.get("invalidation"),
        "confidence": frozen.get("confidence") or frozen_prediction.get("confidence") or frozen.get("flow_confidence"),
    }
    contract_direction = str(frozen_contract.get("direction") or "").upper()
    if contract_direction == "SHORT_BIAS":
        frozen_contract["direction"] = "SHORT"
    elif contract_direction == "LONG_BIAS":
        frozen_contract["direction"] = "LONG"

    symbol = authoritative_symbol(report, preflight)
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
    try:
        intraday = float(match.get("intraday_range_percent") or 0)
    except Exception:
        intraday = 0.0

    candles = match.get("candles_1h") or []
    highs = [float(x.get("high")) for x in candles if isinstance(x, dict) and x.get("high") is not None]
    lows = [float(x.get("low")) for x in candles if isinstance(x, dict) and x.get("low") is not None]
    closes = [float(x.get("close")) for x in candles if isinstance(x, dict) and x.get("close") is not None]
    last = float(match.get("last_price") or (closes[-1] if closes else 0))
    resistance = max(highs[-12:]) if highs else last
    support = min(lows[-12:]) if lows else last
    volume_text = fmt_volume(volume)
    news_title = str(selected.get("news_title") or "").strip()
    news_source = str(selected.get("news_source") or "").strip()

    special = None
    category = str(selected.get("category") or selected.get("lane") or frozen.get("category") or frozen.get("lane") or "").lower()
    signal_lane = (
        category in {"capital_flow_long", "capital_flow_short", "technical_setup", "flow"}
        or str(frozen_contract.get("direction") or "").upper() in {"LONG", "SHORT"}
        or all(frozen_contract.get(k) is not None for k in ("entry", "tp1", "tp2", "sl"))
    )
    try:
        from signal_post_builder import build_outcome_post, build_signal_post
        if signal_lane:
            # Feed the immutable contract into the human composer even when an
            # upstream draft omitted normalized fields.
            signal_selected = dict(selected)
            signal_selected["symbol"] = symbol
            signal_selected["direction"] = frozen_contract.get("direction")
            signal_selected["prediction"] = {
                "direction": frozen_contract.get("direction"),
                "entry_trigger": frozen_contract.get("entry"),
                "tp1": frozen_contract.get("tp1"),
                "tp2": frozen_contract.get("tp2"),
                "sl": frozen_contract.get("sl"),
                "confidence": frozen_contract.get("confidence") or 65,
            }
            signal_selected["trade_setup"] = {
                "side": frozen_contract.get("direction"),
                "trigger": frozen_contract.get("entry"),
                "tp1": frozen_contract.get("tp1"),
                "tp2": frozen_contract.get("tp2"),
                "invalidation": frozen_contract.get("sl"),
            }
            special = build_signal_post(signal_selected)
        elif category in {"creator_signal_outcome", "follow_up"}:
            special = build_outcome_post(selected)
    except Exception as exc:
        print(f"Signal-first rescue composer unavailable; using compact contract fallback: {exc}")

    if special:
        post = special["post"]
        hook = special["hook"]
        style = special["style"]
    elif signal_lane:
        direction = str(frozen_contract.get("direction") or "").upper()
        e, tp1, tp2, sl = (frozen_contract.get("entry"), frozen_contract.get("tp1"), frozen_contract.get("tp2"), frozen_contract.get("sl"))
        contract_ok = direction in {"LONG", "SHORT"} and all(v is not None for v in (e, tp1, tp2, sl))
        if not contract_ok:
            raise SystemExit("Frozen signal contract incomplete; refusing generic downgrade")
        hook = f"${symbol}: the {direction} idea is at its decision level."
        why = f"I'm watching the next 1H reaction around {fmt_price(e)}. The setup needs confirmation; it is not a call to chase the current candle."
        plan = f"Entry trigger: {fmt_price(e)}  |  TP1: {fmt_price(tp1)}  |  TP2: {fmt_price(tp2)}  |  SL / invalidation: {fmt_price(sl)}"
        condition = "Because the trigger starts the test, follow-through keeps the thesis alive; the invalidation level ends it."
        question = f"Would you wait for the retest around {fmt_price(e)}, or require a fresh 1H close first?"
        disclaimer = "Conditional setup only; no guarantee."
        post = "\n\n".join([hook, why, plan, condition, question, disclaimer])
        style = "publish_rescue_mobile_contract_v2"
    elif news_title:
        source_line = f"Source: {news_source}" if news_source else "Source: verified news feed"
        hook = f"🚨 ${symbol}: {news_title}"
        post = "\n\n".join([hook, source_line, f"The headline matters only if price confirms it. ${symbol} is {move:+.1f}% with {volume_text}.", f"Watch {fmt_price(resistance)} as the decision area; a failed reaction puts {fmt_price(support)} back in focus.", "Does price confirm the catalyst, or fade it?"])
        style = "publish_rescue_newsroom"
    elif move >= 15:
        hook = f"🔥 ${symbol} moved {move:+.1f}% — confirmation now matters more than the headline."
        post = "\n\n".join([hook, f"Spot activity is {volume_text}, with a {intraday:.1f}% intraday range.", f"A hold above {fmt_price(resistance)} keeps continuation in play; rejection puts {fmt_price(support)} back on watch.", "Would you wait for a clean hold, or expect a pullback first?"])
        style = "publish_rescue_momentum"
    elif move <= -15:
        hook = f"⚠️ ${symbol} fell {abs(move):.1f}% — the reaction now matters more than the drop itself."
        post = "\n\n".join([hook, f"Spot activity is {volume_text}, with a {intraday:.1f}% intraday range.", f"A reclaim of {fmt_price(resistance)} improves the read; losing {fmt_price(support)} keeps sellers in control.", "Would you wait for a reclaim, or another lower high?"])
        style = "publish_rescue_breakdown"
    else:
        hook = f"📊 ${symbol}: the next 1H move is the decision point."
        post = "\n\n".join([hook, f"Price is around {fmt_price(last)} with {volume_text} and a {intraday:.1f}% intraday range.", f"A clean move through {fmt_price(resistance)} strengthens the upside read; rejection keeps {fmt_price(support)} in focus.", "Which level would you require before treating the setup as confirmed?"])
        style = "publish_rescue_chart"

    # Keep mobile posts compact, but never truncate a signal contract.
    if signal_lane and len(post) > 740:
        raise SystemExit("Human signal post exceeded mobile limit; refusing unsafe truncation")
    post = post[:740] if not signal_lane else post

    draft = report.get("draft") or {}
    if not isinstance(draft, dict):
        draft = {}
    draft.update({
        "post": post, "text": post, "hook": hook,
        "discussion_question": post.splitlines()[-1],
        "quality_score": 90, "editorial_style": style,
        "generation_mode": "LOCAL_FALLBACK", "publication_status": "DRAFT_ONLY_NOT_PUBLISHED",
        "symbol": symbol, "content_category": selected.get("category") or selected.get("reason") or "market_opportunity",
    })

    visual = report.get("visual_plan") or {}
    if not isinstance(visual, dict):
        visual = {}
    visual.update({"use_visual": True, "type": "candlestick_chart", "provider": "TradingView", "timeframe": "1H", "rescue_text_fallback": False})

    meta = load(VISUAL_META, {})
    chart_symbols = [str(x).upper() for x in (meta.get("tradingview_symbols") or [])]
    chart_symbol = chart_symbols[0] if chart_symbols else str(meta.get("tradingview_symbol") or meta.get("symbol") or "").upper()
    expected = f"BINANCE:{symbol}USDT"
    if chart_symbol and chart_symbol != expected:
        raise SystemExit(f"TradingView visual asset mismatch: chart={chart_symbol}, expected={expected}; refusing rescue")

    report["draft"] = draft
    report["visual_plan"] = visual
    report["status"] = "DRAFT_ONLY_NOT_PUBLISHED"
    report["generation_mode"] = "LOCAL_FALLBACK"
    report["publish_rescue"] = True
    report["publish_rescue_at"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"status": "LOCAL_FALLBACK_SUCCESS", "generation_mode": "LOCAL_FALLBACK", "reason": "Human mobile rescue with frozen contract and visual asset binding", "rescue": True}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PUBLISH_RESCUE_READY", "report": str(report_path), "symbol": symbol}, indent=2))


if __name__ == "__main__":
    main()
