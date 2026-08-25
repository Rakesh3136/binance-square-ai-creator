import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

REPORT_DIR = Path("data/reports")
VISUAL_DIR = Path("data/visuals")
LIVE_VISUAL = Path("data/live/visual.png")
VISUAL_DIR.mkdir(parents=True, exist_ok=True)
LIVE_VISUAL.parent.mkdir(parents=True, exist_ok=True)

BG = "#0b0f14"
PANEL = "#111820"
GRID = "#26313c"
TEXT = "#e6edf3"
MUTED = "#8b98a8"
UP = "#19c37d"
DOWN = "#ef5350"
EMA9 = "#f2b84b"
EMA20 = "#7da2ff"
EMA50 = "#c084fc"
SUPPORT = "#39d98a"
RESISTANCE = "#ff7b7b"
ACCENT = "#f5c451"


def latest_report():
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise RuntimeError("No multi-agent report found")
    return reports[0]


def ema(values, span):
    alpha = 2.0 / (span + 1.0)
    out = []
    for value in values:
        out.append(value if not out else alpha * value + (1 - alpha) * out[-1])
    return out


def rsi(values, period=14):
    if len(values) < period + 1:
        return [50.0] * len(values)
    gains, losses = [], []
    for a, b in zip(values[:-1], values[1:]):
        delta = b - a
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result = [50.0] * period
    result.append(100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss)))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result.append(100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss)))
    return result[:len(values)]


def pivot_levels(candles, lookback=2):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        window = candles[i - lookback:i + lookback + 1]
        if h >= max(float(c["high"]) for c in window):
            highs.append((i, h))
        if l <= min(float(c["low"]) for c in window):
            lows.append((i, l))
    return highs, lows


def detect_patterns(candles):
    if len(candles) < 12:
        return []
    closes = [float(c["close"]) for c in candles]
    highs, lows = pivot_levels(candles, 2)
    patterns = []
    recent = closes[-min(18, len(closes)):]
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b[0] - a[0] >= 3:
            midpoint = max(closes[a[0]:b[0] + 1])
            if abs(a[1] - b[1]) / max((a[1] + b[1]) / 2, 1e-12) < .035 and midpoint > max(a[1], b[1]) * 1.02:
                patterns.append("double bottom")
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b[0] - a[0] >= 3:
            valley = min(closes[a[0]:b[0] + 1])
            if abs(a[1] - b[1]) / max((a[1] + b[1]) / 2, 1e-12) < .035 and valley < min(a[1], b[1]) * .98:
                patterns.append("double top")
    if len(recent) >= 12:
        left, middle, right = max(recent[:4]), min(recent[4:10]), max(recent[-4:])
        if middle < left * .94 and right > left * .96 and right < left * 1.04:
            patterns.append("cup and handle")
    return patterns


def _price_decimals(value):
    value = abs(float(value))
    if value >= 1000:
        return 2
    if value >= 1:
        return 4
    if value >= 0.01:
        return 5
    if value >= 0.0001:
        return 7
    return 10


def _style_axis(ax):
    ax.set_facecolor(PANEL)
    ax.grid(True, color=GRID, linewidth=.55, alpha=.55)
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(GRID)
        spine.set_linewidth(.7)


def render_candlestick(symbol, candles, title, output):
    if len(candles) < 20:
        raise RuntimeError(f"Not enough real 1h candles for {symbol}")

    times = [datetime.fromtimestamp(float(c["open_time"]) / 1000, tz=timezone.utc) for c in candles]
    x = mdates.date2num(times)
    opens = [float(c["open"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    closes = [float(c["close"]) for c in candles]
    volumes = [float(c["volume"]) for c in candles]
    decimals = _price_decimals(closes[-1])
    width = max((x[-1] - x[0]) / len(x) * .68, .012)

    fig = plt.figure(figsize=(13.5, 8.5), facecolor=BG)
    ax = fig.add_axes([.075, .30, .89, .56], facecolor=PANEL)
    vol = fig.add_axes([.075, .16, .89, .11], sharex=ax, facecolor=PANEL)
    mom = fig.add_axes([.075, .055, .89, .08], sharex=ax, facecolor=PANEL)
    for axis in (ax, vol, mom):
        _style_axis(axis)

    for t, o, h, l, c, v in zip(x, opens, highs, lows, closes, volumes):
        color = UP if c >= o else DOWN
        ax.vlines(t, l, h, color=color, linewidth=1.0, zorder=2)
        body_low = min(o, c)
        body_height = max(abs(c - o), max(abs(c), 1e-12) * .00003)
        ax.add_patch(Rectangle((t - width / 2, body_low), width, body_height,
                               facecolor=color, edgecolor=color, linewidth=.45, zorder=3))
        vol.bar(t, v, width=width, color=color, alpha=.38, linewidth=0)

    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ax.plot(x, ema9, color=EMA9, linewidth=1.25, label="EMA 9")
    ax.plot(x, ema20, color=EMA20, linewidth=1.25, label="EMA 20")
    ax.plot(x, ema50, color=EMA50, linewidth=1.15, label="EMA 50")

    swing_highs, swing_lows = pivot_levels(candles, 2)
    resistance = swing_highs[-1][1] if swing_highs else None
    support = swing_lows[-1][1] if swing_lows else None
    if resistance is not None:
        ax.axhline(resistance, color=RESISTANCE, linestyle=(0, (4, 4)), linewidth=.85, alpha=.9)
        ax.text(x[-1], resistance, f"R {resistance:.{decimals}f}", color=RESISTANCE,
                va="bottom", ha="right", fontsize=8, fontweight="bold")
    if support is not None:
        ax.axhline(support, color=SUPPORT, linestyle=(0, (4, 4)), linewidth=.85, alpha=.9)
        ax.text(x[-1], support, f"S {support:.{decimals}f}", color=SUPPORT,
                va="top", ha="right", fontsize=8, fontweight="bold")

    momentum = rsi(closes, 14)
    mom.plot(x, momentum, color=ACCENT, linewidth=1.1)
    mom.axhline(70, color=DOWN, linestyle="--", linewidth=.65, alpha=.65)
    mom.axhline(30, color=UP, linestyle="--", linewidth=.65, alpha=.65)
    mom.set_ylim(0, 100)
    mom.set_ylabel("RSI", color=MUTED, fontsize=8)
    vol.set_ylabel("VOL", color=MUTED, fontsize=8)

    first = opens[0]
    last = closes[-1]
    move = ((last - first) / first * 100) if first else 0
    direction = "BULLISH" if closes[-1] >= ema20[-1] else "BEARISH"
    patterns = detect_patterns(candles)
    pattern_text = " • ".join(patterns) if patterns else "No confirmed classical pattern"

    ax.set_title(f"{title or 'Market Structure'}  |  {symbol}", loc="left", fontsize=16,
                 fontweight="bold", color=TEXT, pad=12)
    ax.text(.995, 1.015, f"{move:+.2f}%  •  {direction}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=10, color=UP if move >= 0 else DOWN, fontweight="bold")
    ax.text(.995, .965, f"1H • {pattern_text}", transform=ax.transAxes,
            ha="right", va="top", fontsize=8.5, color=MUTED)
    ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor=MUTED, ncol=3)
    ax.set_ylabel("Price (USDT)", color=MUTED, fontsize=8)
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.{decimals}f}"))

    locator = mdates.AutoDateLocator(minticks=5, maxticks=8)
    formatter = mdates.DateFormatter("%d %b %H:%M", tz=timezone.utc)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.tick_params(axis="x", labelbottom=False)
    vol.tick_params(axis="x", labelbottom=False)
    mom.xaxis.set_major_locator(locator)
    mom.xaxis.set_major_formatter(formatter)

    fig.text(.075, .018, "BINANCE MARKET DATA • 1H OHLCV • EMA 9/20/50 • RSI 14 • For education, not financial advice",
             fontsize=8.2, color=MUTED)
    fig.text(.965, .018, "AUTONOMOUS CREATOR", ha="right", fontsize=8.2, color=MUTED)
    fig.savefig(output, dpi=190, bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def main():
    report_path = latest_report()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    market = report.get("live_market_snapshot") or {}

    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status": "NO_VISUAL_REQUESTED", "report": str(report_path)}))
        return 0

    signals = market.get("top_content_signals") or []
    if not signals:
        print(json.dumps({"status": "NO_MARKET_DATA_FOR_VISUAL", "report": str(report_path)}))
        return 0

    output = VISUAL_DIR / (report_path.stem + ".png")
    chart_type = plan.get("type")
    selected = None

    if chart_type == "candlestick_chart":
        requested = [str(x.get("symbol", "")).upper() for x in plan.get("data_points", []) if isinstance(x, dict)]
        selected = next((s for s in signals if str(s.get("symbol", "")).upper() in requested and s.get("candles_1h")), None)
        selected = selected or next((s for s in signals if s.get("candles_1h")), None)
        if not selected:
            print(json.dumps({"status": "VISUAL_SKIPPED_NO_REAL_CANDLES", "report": str(report_path)}))
            return 0
        render_candlestick(selected["symbol"], selected["candles_1h"], plan.get("title"), output)
    else:
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        values = [float(x.get("price_change_percent", 0)) for x in data]
        fig, ax = plt.subplots(figsize=(12, 7), facecolor=BG)
        _style_axis(ax)
        bars = ax.bar(labels, values, color=[UP if v >= 0 else DOWN for v in values])
        ax.axhline(0, color=MUTED, linewidth=.8)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:+.1f}%", ha="center",
                    va="bottom" if value >= 0 else "top", color=TEXT, fontsize=9)
        ax.set_title(plan.get("title") or "Market comparison", color=TEXT, loc="left", fontweight="bold")
        ax.set_ylabel("24H change (%)", color=MUTED)
        fig.tight_layout()
        fig.savefig(output, dpi=190, bbox_inches="tight", facecolor=BG)
        plt.close(fig)

    shutil.copy2(output, LIVE_VISUAL)
    print(json.dumps({
        "status": "VISUAL_CREATED",
        "type": chart_type,
        "output": str(output),
        "publish_output": str(LIVE_VISUAL),
        "style": "professional_dark_candlestick",
        "data_source": "Binance public market data",
        "indicators": ["EMA 9", "EMA 20", "EMA 50", "RSI 14", "Volume"],
        "patterns_detected": detect_patterns(selected["candles_1h"]) if selected and chart_type == "candlestick_chart" else []
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
