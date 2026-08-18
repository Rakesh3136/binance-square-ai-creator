import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Binance documents data-api.binance.vision as the dedicated unauthenticated
# public market-data endpoint. GitHub-hosted runners can receive HTTP 451 from
# api.binance.com because of regional/service restrictions, so use the market-data
# domain first and keep a couple of documented public endpoints as fallbacks.
BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
]
OUTPUT = Path("data/live/market_snapshot.json")
QUOTE = os.getenv("MARKET_QUOTE", "USDT")
TOP_N = int(os.getenv("MARKET_TOP_N", "40"))


def get_json(path: str, params: dict | None = None):
    last_error = None
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    for base in BINANCE_BASES:
        url = base + path + query
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "binance-square-ai-creator/1.0",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            last_error = exc
            continue

    raise RuntimeError(f"All Binance public market-data endpoints failed: {last_error}")


def main() -> None:
    tickers = get_json("/api/v3/ticker/24hr", {"type": "FULL"})
    candidates = []
    for item in tickers:
        symbol = item.get("symbol", "")
        if not symbol.endswith(QUOTE):
            continue
        try:
            pct = float(item.get("priceChangePercent", 0))
            quote_volume = float(item.get("quoteVolume", 0))
            high = float(item.get("highPrice", 0))
            low = float(item.get("lowPrice", 0))
            last = float(item.get("lastPrice", 0))
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0 or last <= 0:
            continue
        range_pct = ((high - low) / last) * 100 if last else 0
        # Content opportunity, not investment potential.
        score = min(100.0, abs(pct) * 4 + range_pct * 1.5 + min(20.0, quote_volume / 50_000_000))
        candidates.append({
            "symbol": symbol,
            "price_change_percent": round(pct, 4),
            "last_price": last,
            "quote_volume_usdt": round(quote_volume, 2),
            "intraday_range_percent": round(range_pct, 4),
            "content_signal_score": round(score, 2),
        })

    movers = sorted(candidates, key=lambda x: x["content_signal_score"], reverse=True)[:TOP_N]
    top_gainers = sorted(candidates, key=lambda x: x["price_change_percent"], reverse=True)[:10]
    top_losers = sorted(candidates, key=lambda x: x["price_change_percent"])[:10]
    highest_volume = sorted(candidates, key=lambda x: x["quote_volume_usdt"], reverse=True)[:10]

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Spot public 24hr ticker endpoint",
        "quote": QUOTE,
        "top_content_signals": movers,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "highest_volume": highest_volume,
        "note": "Market figures are observations for content research, not trading advice or price predictions.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "symbols_scanned": len(candidates),
        "top_signal": movers[0] if movers else None,
        "output": str(OUTPUT),
    }, indent=2))


if __name__ == "__main__":
    main()
