"""Capital-flow rotation intelligence for the existing Creator pipeline.

Uses only public Binance Spot observations. This is a content-research signal,
not a guarantee or trading advice. It ranks relative flow/strength evidence
across liquid USDT assets and produces a frozen-friendly signal for downstream
opportunity selection.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/capital_flow_intelligence.json"
BASES = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
]
MAX_ASSETS = 80
MIN_QUOTE_VOLUME = 5_000_000


def get_json(path: str, params: dict) -> object:
    query = urllib.parse.urlencode(params)
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(
                base + path + "?" + query,
                headers={"User-Agent": "binance-square-ai-creator/capital-flow"},
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))


def num(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def candles(symbol: str) -> list[list]:
    data = get_json("/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": 24})
    return data if isinstance(data, list) else []


def signal(symbol: str) -> dict | None:
    try:
        rows = candles(symbol)
    except Exception:
        return None
    if len(rows) < 18:
        return None
    closes = [num(row[4]) for row in rows]
    vols = [num(row[5]) for row in rows]
    if closes[-12] <= 0:
        return None

    ret_12h = (closes[-1] / closes[-12] - 1.0) * 100
    ret_6h = (closes[-1] / closes[-7] - 1.0) * 100
    recent_vol = sum(vols[-6:]) / 6
    prior_vol = sum(vols[-18:-6]) / 12
    volume_ratio = recent_vol / prior_vol if prior_vol > 0 else 1.0

    # Directional pressure proxy: signed hourly returns weighted by quote volume.
    pressure = 0.0
    denom = 0.0
    for i in range(1, len(rows)):
        previous = closes[i - 1]
        move = (closes[i] / previous - 1.0) * 100 if previous else 0.0
        volume = vols[i]
        pressure += move * volume
        denom += volume
    pressure_pct = pressure / denom if denom else 0.0

    score = (
        ret_12h * 3
        + ret_6h * 2
        + max(-2, min(2, volume_ratio - 1)) * 8
        + pressure_pct * 4
    )
    return {
        "symbol": symbol,
        "return_6h_pct": round(ret_6h, 4),
        "return_12h_pct": round(ret_12h, 4),
        "volume_ratio_6h_vs_prior_12h": round(volume_ratio, 4),
        "volume_pressure_pct": round(pressure_pct, 5),
        "flow_score": round(score, 4),
    }


def select_assets(tickers: list[dict]) -> list[tuple[str, float]]:
    eligible = []
    for item in tickers:
        symbol = str(item.get("symbol") or "")
        if not symbol.endswith("USDT"):
            continue
        quote_volume = num(item.get("quoteVolume"))
        if quote_volume < MIN_QUOTE_VOLUME:
            continue
        change = abs(num(item.get("priceChangePercent")))
        eligible.append((symbol, quote_volume, change))

    # Bound the OHLCV fan-out. We deliberately combine liquidity leaders and
    # large movers so the scanner can see both established rotation and fresh
    # flow without making hundreds of API requests per creator cycle.
    liquidity = sorted(eligible, key=lambda x: x[1], reverse=True)[:50]
    movers = sorted(eligible, key=lambda x: x[2], reverse=True)[:30]
    merged: dict[str, float] = {}
    for symbol, quote_volume, _ in liquidity + movers:
        merged[symbol] = quote_volume
    for symbol in ("BTCUSDT", "ETHUSDT", "BNBUSDT"):
        for candidate, quote_volume, _ in eligible:
            if candidate == symbol:
                merged[symbol] = quote_volume
                break
    return list(merged.items())[:MAX_ASSETS]


def main() -> int:
    tickers = get_json("/api/v3/ticker/24hr", {"type": "FULL"})
    ticker_rows = tickers if isinstance(tickers, list) else []
    selected = select_assets(ticker_rows)

    rows = []
    quote_by_symbol = dict(selected)
    for symbol, _ in selected:
        result = signal(symbol)
        if result:
            result["quote_volume_usdt"] = round(quote_by_symbol[symbol], 2)
            rows.append(result)

    rows.sort(key=lambda item: item["flow_score"], reverse=True)
    leaders = rows[:5]
    laggards = sorted(rows, key=lambda item: item["flow_score"])[:5]
    rotation = (
        "RISK_ON_ROTATION"
        if leaders and sum(item["flow_score"] for item in leaders) > 0
        else "RISK_OFF_OR_DEFENSIVE"
    )
    if leaders and laggards:
        spread = (
            sum(item["flow_score"] for item in leaders) / len(leaders)
            - sum(item["flow_score"] for item in laggards) / len(laggards)
        )
    else:
        spread = 0.0

    result = {
        "version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Binance Spot 24h ticker + 1h OHLCV",
        "method": "relative strength + volume acceleration + volume-weighted directional pressure",
        "assets_considered": len(selected),
        "assets_scored": len(rows),
        "rotation_state": rotation,
        "leader_laggard_spread": round(spread, 4),
        "leaders": leaders,
        "laggards": laggards,
        "highest_conviction": leaders[0] if leaders else None,
        "constraints": [
            "observational signal only",
            "capital flow is a market-data proxy, not wallet-level fund-flow data",
            "no guaranteed pump/short claim",
            "no synthetic data",
            "requires editorial and technical gates before publication",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "OK",
        "assets_considered": len(selected),
        "assets_scored": len(rows),
        "rotation_state": rotation,
        "highest_conviction": result["highest_conviction"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
