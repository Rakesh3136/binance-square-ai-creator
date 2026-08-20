import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

REPORT_DIR = Path("data/reports")
VISUAL_DIR = Path("data/visuals")
VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def latest_report() -> Path:
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise RuntimeError("No multi-agent report found")
    return reports[0]


def render_candlestick(symbol: str, candles: list[dict], title: str, output: Path) -> None:
    """Render only real Binance OHLCV observations; never synthesize candles."""
    if len(candles) < 3:
        raise RuntimeError(f"Not enough real 1h candles for {symbol}")

    times = [datetime.fromtimestamp(c["open_time"] / 1000, tz=timezone.utc) for c in candles]
    x = mdates.date2num(times)
    width = max((x[-1] - x[0]) / max(len(x), 1) * 0.62, 0.012)

    fig = plt.figure(figsize=(12, 8), facecolor="#10151c")
    ax_price = fig.add_axes([0.08, 0.20, 0.88, 0.66], facecolor="#151b23")
    ax_volume = fig.add_axes([0.08, 0.09, 0.88, 0.11], sharex=ax_price, facecolor="#151b23")

    for t, candle in zip(x, candles):
        open_price = candle["open"]
        close_price = candle["close"]
        high = candle["high"]
        low = candle["low"]
        up = close_price >= open_price
        body_low = min(open_price, close_price)
        body_height = max(abs(close_price - open_price), max(abs(close_price), 1e-12) * 0.00005)
        candle_color = "#20c997" if up else "#ff5c5c"

        ax_price.vlines(t, low, high, color=candle_color, linewidth=1.2, zorder=2)
        ax_price.add_patch(Rectangle(
            (t - width / 2, body_low),
            width,
            body_height,
            facecolor=candle_color,
            edgecolor=candle_color,
            linewidth=0.8,
            zorder=3,
        ))
        ax_volume.bar(t, candle["volume"], width=width, color=candle_color, alpha=0.55)

    last = candles[-1]["close"]
    first = candles[0]["open"]
    move = ((last - first) / first * 100) if first else 0

    ax_price.axhline(last, linewidth=0.9, linestyle="--", color="#aab4c3", alpha=0.7)
    ax_price.text(
        0.995, last, f"  {last:.8g}", transform=ax_price.get_yaxis_transform(),
        va="center", ha="left", fontsize=10, color="#e8edf3",
    )
    ax_price.set_title(
        f"{title}\n{symbol} • 1H real Binance OHLCV • {move:+.2f}% across displayed candles",
        loc="left", fontsize=17, fontweight="bold", color="#f4f7fa", pad=14,
    )
    ax_price.set_ylabel("Price (USDT)", color="#b9c2cf")
    ax_volume.set_ylabel("Volume", color="#b9c2cf")
    ax_volume.set_xlabel("UTC time", color="#b9c2cf")

    for ax in (ax_price, ax_volume):
        ax.grid(True, alpha=0.12, linewidth=0.7)
        ax.tick_params(colors="#b9c2cf", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#303945")

    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    ax_price.tick_params(axis="x", labelbottom=False)
    ax_volume.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=8))
    ax_volume.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))

    fig.text(
        0.08, 0.035,
        "Source: Binance Spot public market data • Candles are observations, not predictions or trading advice",
        fontsize=9, color="#8e99a8",
    )
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    report_path = latest_report()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    market = report.get("live_market_snapshot") or {}

    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status": "NO_VISUAL_REQUESTED", "report": str(report_path)}, indent=2))
        return

    signals = market.get("top_content_signals") or []
    if not signals:
        print(json.dumps({"status": "NO_MARKET_DATA_FOR_VISUAL", "report": str(report_path)}, indent=2))
        return

    chart_type = plan.get("type")
    title = plan.get("title") or "Market snapshot"
    output = VISUAL_DIR / (report_path.stem + ".png")

    if chart_type == "candlestick_chart":
        # Prefer the symbol explicitly selected by the model; otherwise use the
        # strongest content signal. Only use a candle series that the scanner
        # actually retrieved from Binance.
        requested_symbols = [str(x.get("symbol", "")).upper() for x in (plan.get("data_points") or []) if isinstance(x, dict)]
        selected = None
        for signal in signals:
            if signal.get("symbol", "").upper() in requested_symbols and signal.get("candles_1h"):
                selected = signal
                break
        if selected is None:
            selected = next((x for x in signals if x.get("candles_1h")), None)
        if selected is None:
            print(json.dumps({
                "status": "VISUAL_SKIPPED_NO_REAL_CANDLES",
                "report": str(report_path),
                "reason": "No real Binance 1h OHLCV candles were available; refusing to synthesize a chart.",
            }, indent=2))
            return
        render_candlestick(selected["symbol"], selected["candles_1h"], title, output)

    elif chart_type in {"market_bar_chart", "market_comparison"}:
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        values = [float(x.get("price_change_percent", 0)) for x in data]
        plt.figure(figsize=(12, 7))
        plt.bar(labels, values)
        plt.axhline(0, linewidth=1)
        plt.title(title)
        plt.ylabel("24h price change (%)")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        plt.savefig(output, dpi=180, bbox_inches="tight")
        plt.close()

    elif chart_type == "market_range_chart":
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        # This range is the observed 24h high/low from Binance, not an
        # approximation derived from intraday_range_percent.
        lows = []
        highs = []
        centers = []
        for item in data:
            candles = item.get("candles_1h") or []
            if candles:
                lows.append(min(float(c["low"]) for c in candles))
                highs.append(max(float(c["high"]) for c in candles))
                centers.append(float(candles[-1]["close"]))
            else:
                lows.append(float(item.get("last_price", 0)))
                highs.append(float(item.get("last_price", 0)))
                centers.append(float(item.get("last_price", 0)))
        plt.figure(figsize=(12, 7))
        plt.vlines(range(len(labels)), lows, highs, linewidth=3)
        plt.scatter(range(len(labels)), centers)
        plt.xticks(range(len(labels)), labels, rotation=35, ha="right")
        plt.title(title)
        plt.ylabel("Observed 24h price range (USDT)")
        plt.tight_layout()
        plt.savefig(output, dpi=180, bbox_inches="tight")
        plt.close()

    else:
        # Conservative fallback: a text card is allowed, but never pretend it is
        # a financial chart when the underlying data cannot support one.
        plt.figure(figsize=(12, 7))
        plt.axis("off")
        text = plan.get("caption") or plan.get("purpose") or title
        plt.text(0.05, 0.88, title, fontsize=20, va="top", wrap=True)
        plt.text(0.05, 0.72, text, fontsize=13, va="top", wrap=True)
        plt.tight_layout()
        plt.savefig(output, dpi=180, bbox_inches="tight")
        plt.close()

    print(json.dumps({
        "status": "VISUAL_CREATED",
        "type": chart_type,
        "output": str(output),
        "caption": plan.get("caption", ""),
        "alt_text": plan.get("alt_text", ""),
    }, indent=2))


if __name__ == "__main__":
    main()
