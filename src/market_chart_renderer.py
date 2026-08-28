"""Render a data-accurate candlestick chart when TradingView cannot be captured in CI.

This is explicitly NOT presented as a TradingView screenshot. It uses fresh Binance
OHLCV already collected by live_market_scanner.py and can carry the same verified
support/resistance/target/invalidation levels into the visual.
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/visual.png"
META = ROOT / "data/live/visual_metadata.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    frozen = load(ROOT / "data/live/authoritative_opportunity.json")
    context = load(ROOT / "data/live/publication_context.json")
    snapshot = load(ROOT / "data/live/market_snapshot.json")
    symbol = str(frozen.get("symbol") or context.get("symbol") or "").upper().replace("USDT", "")
    if not symbol:
        raise SystemExit("No frozen symbol for chart fallback")

    item = None
    target = symbol + "USDT"
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for row in snapshot.get(group) or []:
            if isinstance(row, dict) and str(row.get("symbol", "")).upper() == target:
                item = row
                break
        if item:
            break
    candles = (item or {}).get("candles_1h") or []
    if len(candles) < 6:
        raise SystemExit(f"Fresh Binance OHLCV is unavailable for {target}; refusing synthetic chart")

    candles = candles[-24:]
    fig, ax = plt.subplots(figsize=(14, 8), dpi=140)
    width = 0.62
    for i, c in enumerate(candles):
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        ax.vlines(i, l, h, linewidth=1.1)
        lower = min(o, cl)
        height = max(abs(cl - o), max((h-l)*0.002, 1e-12))
        rect = Rectangle((i-width/2, lower), width, height,
                         fill=(cl >= o), alpha=0.8, linewidth=0.8)
        ax.add_patch(rect)

    # Prefer levels calculated by technical_enricher when present in the draft report.
    levels = {}
    reports = sorted((ROOT / "data/reports").glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if reports:
        try:
            levels = (load(reports[0]).get("research") or {}).get("chart_levels") or {}
        except Exception:
            levels = {}
    if levels:
        labels = (("support", "Support"), ("resistance", "Resistance"), ("target", "Target"), ("invalidation", "Invalidation"))
        for key, label in labels:
            value = levels.get(key)
            if value is not None:
                ax.axhline(float(value), linewidth=1.0, linestyle="--", alpha=0.75)
                ax.text(len(candles)-0.2, float(value), f" {label} {float(value):.8g}", va="center", fontsize=9)

    ax.set_title(f"BINANCE:{symbol}USDT • 1H • Fresh Binance OHLCV", fontsize=16, loc="left")
    ax.set_ylabel("Price")
    ax.set_xlim(-1, len(candles))
    ax.grid(True, alpha=0.18)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="png", bbox_inches="tight")
    plt.close(fig)
    size = OUT.stat().st_size
    if size < 30000:
        raise SystemExit(f"Fallback chart unexpectedly small: {size} bytes")
    META.write_text(json.dumps({
        "status": "BINANCE_OHLCV_FALLBACK",
        "provider": "Binance public market data",
        "tradingview_capture": False,
        "base_symbol": symbol,
        "tradingview_symbol": f"BINANCE:{symbol}USDT",
        "timeframe": "1H",
        "output": str(OUT),
        "bytes": size,
        "candles": len(candles),
        "reason": "TradingView capture unavailable in GitHub Actions runner",
    }, indent=2), encoding="utf-8")
    print(json.dumps({"status":"BINANCE_OHLCV_FALLBACK","symbol":symbol,"candles":len(candles),"bytes":size}))


if __name__ == "__main__":
    main()
