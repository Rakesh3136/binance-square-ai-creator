import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
]
OUTPUT = Path("data/live/market_snapshot.json")
QUOTE = os.getenv("MARKET_QUOTE", "USDT")
TOP_N = int(os.getenv("MARKET_TOP_N", "40"))
CANDLE_COUNT = int(os.getenv("MARKET_CANDLE_COUNT", "24"))


def get_json(path: str, params: dict | None = None):
    last_error = None
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    for base in BINANCE_BASES:
        url = base + path + query
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "binance-square-ai-creator/1.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            last_error = exc
    raise RuntimeError(f"All Binance public market-data endpoints failed: {last_error}")


def fetch_1h_candles(symbol: str) -> list[dict]:
    raw = get_json("/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": CANDLE_COUNT})
    candles = []
    for row in raw:
        try:
            candles.append({
                "open_time": int(row[0]), "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
            })
        except (TypeError, ValueError, IndexError):
            continue
    return candles


def fetch_new_listings() -> list[dict]:
    """Return recently onboarded spot symbols when Binance exposes onboardDate.

    This is deliberately best-effort: if the endpoint omits onboardDate, we do not
    invent listing dates and simply return an empty list.
    """
    try:
        info = get_json("/api/v3/exchangeInfo", {"symbolStatus": "TRADING"})
    except Exception:
        return []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff_ms = now_ms - 30 * 24 * 60 * 60 * 1000
    results = []
    for item in info.get("symbols") or []:
        symbol = str(item.get("symbol") or "")
        if not symbol.endswith(QUOTE):
            continue
        try:
            onboard = int(item.get("onboardDate"))
        except (TypeError, ValueError):
            continue
        if onboard >= cutoff_ms:
            results.append({
                "symbol": symbol,
                "onboard_date": datetime.fromtimestamp(onboard / 1000, tz=timezone.utc).isoformat(),
                "days_since_listing": round((now_ms - onboard) / 86_400_000, 2),
            })
    return sorted(results, key=lambda x: x["onboard_date"], reverse=True)[:15]


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
    new_listings = fetch_new_listings()

    listing_symbols = {x["symbol"] for x in new_listings}
    for row in candidates:
        if row["symbol"] in listing_symbols:
            match = next(x for x in new_listings if x["symbol"] == row["symbol"])
            row["new_listing"] = True
            row["onboard_date"] = match["onboard_date"]
            row["days_since_listing"] = match["days_since_listing"]
    new_listing_market = [x for x in candidates if x.get("new_listing")]
    new_listing_market.sort(key=lambda x: (x.get("days_since_listing", 999), -x["content_signal_score"]))
    new_listing_market = new_listing_market[:10]

    candle_failures = []
    for signal in movers[:6]:
        try:
            signal["candles_1h"] = fetch_1h_candles(signal["symbol"])
        except Exception as exc:
            signal["candles_1h"] = []
            candle_failures.append({"symbol": signal["symbol"], "error": str(exc)})

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Spot public 24hr ticker + public 1h klines + exchangeInfo",
        "quote": QUOTE,
        "top_content_signals": movers,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "highest_volume": highest_volume,
        "new_listings": new_listings,
        "new_listing_market": new_listing_market,
        "candle_failures": candle_failures,
        "content_categories": [
            "top_gainers", "top_losers", "volume_leaders", "new_listings",
            "high_volatility", "BTC_ETH_market_context", "news_and_macro"
        ],
        "note": "Market figures are observations for content research, not trading advice or price predictions. Candles are real Binance OHLCV observations; no synthetic price data is generated.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "symbols_scanned": len(candidates),
        "top_signal": movers[0] if movers else None,
        "top_gainer": top_gainers[0] if top_gainers else None,
        "top_loser": top_losers[0] if top_losers else None,
        "new_listings_found": len(new_listings),
        "candles_attached": sum(1 for x in movers[:6] if x.get("candles_1h")),
        "candle_failures": candle_failures,
        "output": str(OUTPUT),
    }, indent=2))


if __name__ == "__main__":
    main()
