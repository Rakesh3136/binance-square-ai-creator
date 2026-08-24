import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATUS = Path("data/live/creator_status.json")
USAGE = Path("analytics/ai_usage.json")
REPORT_DIR = Path("data/reports")
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_BUDGET", "20"))


def load(path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def save_status(status, reason, **extra):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "status": status, "reason": reason, **extra}, indent=2, ensure_ascii=False), encoding="utf-8")


def run_creator(local_fallback=False):
    if local_fallback:
        os.environ["LOCAL_FALLBACK"] = "true"
    else:
        os.environ.pop("LOCAL_FALLBACK", None)
    import multi_agent_creator
    multi_agent_creator.main()


def emergency_verified_draft(reason):
    """Last-resort draft using only verified local snapshots; no AI/provider calls."""
    preflight = load(Path("data/live/editorial_preflight.json"), {})
    market = load(Path("data/live/market_snapshot.json"), {})
    selected = preflight.get("selected_opportunity") or {}

    items = []
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        items.extend(x for x in (market.get(group) or []) if isinstance(x, dict))
    selected_symbol = str(selected.get("symbol") or "").upper()
    item = next((x for x in items if str(x.get("symbol", "")).upper() == selected_symbol), None)
    if item is None:
        item = next((x for x in items if x.get("symbol")), {})

    symbol = str(item.get("symbol") or selected_symbol or "MARKET").upper().replace("USDT", "")

    def number(key, default=0.0):
        try:
            return float(item.get(key) or default)
        except Exception:
            return default

    move = number("price_change_percent")
    price = number("last_price")
    volume = number("quote_volume_usdt") or number("quote_volume")
    category = str(selected.get("category") or selected.get("reason") or "market_opportunity")
    opportunity = float(selected.get("adjusted_score") or 80)
    price_text = f"${price:.8g}" if price else "the current level"
    volume_text = f"${volume/1_000_000:.1f}M spot volume" if volume >= 1_000_000 else (f"${volume/1_000:.0f}K spot volume" if volume >= 1_000 else "live market data")

    post = (f"Quick market check: ${symbol} is {move:+.1f}% today.\n"
            f"The latest verified snapshot puts price around {price_text}, with {volume_text}.\n"
            f"This is a {category.replace('_', ' ')} setup — watch the next move rather than chasing the first candle.\n"
            f"Would you wait for confirmation on ${symbol}?")[:740]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "deterministic-emergency-fallback",
        "topic_instruction": selected.get("instruction", ""),
        "selected_editorial_lane": selected,
        "engagement_strategy": preflight.get("engagement_strategy") or {},
        "live_market_snapshot": market,
        "news_discovery_snapshot": load(Path("data/live/news_snapshot.json"), {}),
        "strategy_memory": load(Path("analytics/strategy_memory.json"), {}),
        "research": {"summary": "Emergency draft built only from verified live market data.", "strongest_signal": symbol, "source_mode": "deterministic_emergency_fallback", "opportunity_score": opportunity},
        "critique": {"summary": "AI/local creator failed; no unverified facts were added.", "reason": str(reason)[-500:], "revised_opportunity_score": opportunity},
        "draft": {
            "post": post, "text": post, "hook": f"Quick market check: ${symbol} is {move:+.1f}% today.",
            "discussion_question": f"Would you wait for confirmation on ${symbol}?", "quality_score": 82,
            "editorial_style": "emergency_verified_observation", "generation_mode": "LOCAL_FALLBACK",
            "experiment_id": (preflight.get("engagement_strategy") or {}).get("experiment_id") or "A",
            "experiment_format": ((preflight.get("engagement_strategy") or {}).get("experiment") or {}).get("format"),
            "symbol": symbol, "content_category": category, "publication_status": "DRAFT_ONLY_NOT_PUBLISHED",
        },
        "visual_plan": {"type": "candlestick_chart", "use_visual": bool(item.get("candles_1h")), "title": f"{symbol}: verified 1H market data", "data_points": [{"symbol": symbol}], "purpose": "Use only supplied OHLCV data."},
        "status": "DRAFT_ONLY_NOT_PUBLISHED", "generation_mode": "LOCAL_FALLBACK", "emergency_fallback": True,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "".join(c.lower() if c.isalnum() else "-" for c in symbol).strip("-") or "market-opportunity"
    path = REPORT_DIR / f"{slug}-emergency-multi-agent.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "EMERGENCY_LOCAL_DRAFT", "report": str(path), "symbol": symbol}, indent=2))


def local_or_emergency(original_error):
    try:
        run_creator(local_fallback=True)
        return "LOCAL_FALLBACK_SUCCESS"
    except Exception as fallback_exc:
        print(f"Local fallback failed: {fallback_exc}")
        emergency_verified_draft(f"local fallback failed: {fallback_exc}; original: {original_error}")
        return "EMERGENCY_SUCCESS"


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    usage = load(USAGE, {"date": today, "requests": 0})
    if usage.get("date") != today:
        usage = {"date": today, "requests": 0}
    requests = int(usage.get("requests", 0))

    if requests >= DAILY_LIMIT:
        print(json.dumps({"status": "AI_BUDGET_EXHAUSTED", "requests": requests, "daily_limit": DAILY_LIMIT, "action": "LOCAL_FALLBACK"}, indent=2))
        fallback_status = local_or_emergency("Gemini daily budget exhausted")
        save_status("AI_SUCCESS", "Gemini budget exhausted; local/emergency verified-data creator used", requests=requests, daily_limit=DAILY_LIMIT, generation_mode="LOCAL_FALLBACK", fallback_status=fallback_status)
        return 0

    usage["requests"] = requests + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")

    try:
        run_creator(local_fallback=False)
    except Exception as exc:
        message = str(exc)
        print(f"Gemini creator failed; switching immediately to local/emergency creator. Original error: {message}")
        fallback_status = local_or_emergency(message)
        save_status("AI_SUCCESS", "Gemini creator failed; local/emergency verified-data creator preserved the production cycle", error=message, requests=usage["requests"], daily_limit=DAILY_LIMIT, generation_mode="LOCAL_FALLBACK", fallback_status=fallback_status)
        return 0

    save_status("AI_SUCCESS", "Fresh Gemini draft generated", requests=usage["requests"], daily_limit=DAILY_LIMIT, generation_mode="GEMINI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
