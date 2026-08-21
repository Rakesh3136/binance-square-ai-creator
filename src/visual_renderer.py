import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

REPORT_DIR = Path("data/reports")
VISUAL_DIR = Path("data/visuals")
VISUAL_DIR.mkdir(parents=True, exist_ok=True)


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


def sma(values, period):
    return [sum(values[max(0, i - period + 1): i + 1]) / len(values[max(0, i - period + 1): i + 1]) for i in range(len(values))]


def pivot_levels(candles, lookback=2):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        if h >= max(float(c["high"]) for c in candles[i - lookback:i + lookback + 1]): highs.append((i, h))
        if l <= min(float(c["low"]) for c in candles[i - lookback:i + lookback + 1]): lows.append((i, l))
    return highs, lows


def detect_patterns(candles):
    if len(candles) < 12:
        return []
    closes = [float(c["close"]) for c in candles]
    highs, lows = pivot_levels(candles, 2)
    patterns = []
    recent = closes[-min(18, len(closes)):]

    # W / double-bottom: two nearby swing lows with a higher midpoint.
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        low1, low2 = a[1], b[1]
        if b[0] - a[0] >= 3:
            midpoint = max(closes[a[0]:b[0] + 1])
            if abs(low1 - low2) / max((low1 + low2) / 2, 1e-12) < 0.035 and midpoint > max(low1, low2) * 1.02:
                patterns.append("double_bottom_W")

    # M / double-top.
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        hi1, hi2 = a[1], b[1]
        if b[0] - a[0] >= 3:
            valley = min(closes[a[0]:b[0] + 1])
            if abs(hi1 - hi2) / max((hi1 + hi2) / 2, 1e-12) < 0.035 and valley < min(hi1, hi2) * 0.98:
                patterns.append("double_top_M")

    # Cup-like rounded recovery: left high, deep middle, right recovery near left high.
    if len(recent) >= 12:
        left = max(recent[:4])
        middle = min(recent[4:10])
        right = max(recent[-4:])
        if middle < left * 0.94 and right > left * 0.96 and right < left * 1.04:
            patterns.append("cup_and_handle")

    return patterns


def render_candlestick(symbol, candles, title, output, annotations=None):
    if len(candles) < 8:
        raise RuntimeError(f"Not enough real 1h candles for {symbol}")
    annotations = annotations or []
    times = [datetime.fromtimestamp(c["open_time"] / 1000, tz=timezone.utc) for c in candles]
    x = mdates.date2num(times)
    closes = [float(c["close"]) for c in candles]
    width = max((x[-1] - x[0]) / len(x) * 0.62, 0.012)
    fig = plt.figure(figsize=(12, 8), facecolor="#0f141b")
    ax = fig.add_axes([0.07, 0.20, 0.90, 0.67], facecolor="#141a22")
    vol = fig.add_axes([0.07, 0.08, 0.90, 0.10], sharex=ax, facecolor="#141a22")

    for t, c in zip(x, candles):
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        up = cl >= o
        color = "#22c99a" if up else "#ff5b62"
        ax.vlines(t, l, h, color=color, linewidth=1.1, zorder=2)
        ax.add_patch(Rectangle((t - width / 2, min(o, cl)), width, max(abs(cl - o), max(abs(cl), 1e-12) * 0.00005), facecolor=color, edgecolor=color, linewidth=0.7, zorder=3))
        vol.bar(t, float(c["volume"]), width=width, color=color, alpha=0.45)

    e9, e20 = ema(closes, 9), ema(closes, 20)
    ax.plot(x, e9, color="#f2b84b", linewidth=1.1, label="EMA 9")
    ax.plot(x, e20, color="#8da7ff", linewidth=1.1, label="EMA 20")

    swing_highs, swing_lows = pivot_levels(candles, 2)
    if swing_highs:
        resistance = swing_highs[-1][1]
        ax.axhline(resistance, color="#ff8a8a", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.text(x[-1], resistance, f"  R {resistance:.8g}", va="bottom", fontsize=9, color="#ffb0b0")
    if swing_lows:
        support = swing_lows[-1][1]
        ax.axhline(support, color="#7fe0bb", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.text(x[-1], support, f"  S {support:.8g}", va="top", fontsize=9, color="#9ff0d0")

    patterns = detect_patterns(candles)
    if "double_bottom_W" in patterns and len(swing_lows) >= 2:
        pts = swing_lows[-2:]
        ax.plot([x[p[0]] for p in pts], [p[1] for p in pts], color="#ffcf66", linewidth=2.0)
        ax.annotate("W / double bottom", (x[pts[-1][0]], pts[-1][1]), xytext=(-90, -30), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": "#ffcf66"}, color="#ffcf66", fontsize=9)
    if "double_top_M" in patterns and len(swing_highs) >= 2:
        pts = swing_highs[-2:]
        ax.plot([x[p[0]] for p in pts], [p[1] for p in pts], color="#ffcf66", linewidth=2.0)
        ax.annotate("M / double top", (x[pts[-1][0]], pts[-1][1]), xytext=(-90, 25), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": "#ffcf66"}, color="#ffcf66", fontsize=9)
    if "cup_and_handle" in patterns:
        ax.text(0.01, 0.03, "Detected structure: cup-like recovery", transform=ax.transAxes, color="#ffcf66", fontsize=9)

    # Detect a factual breakout/retest from the latest pivot resistance.
    if swing_highs:
        r = swing_highs[-1][1]
        if closes[-1] > r * 1.005:
            ax.annotate("Breakout", (x[-1], closes[-1]), xytext=(-65, 35), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": "#5de0b1"}, color="#78edc5", fontsize=10, fontweight="bold")
        elif len(closes) >= 3 and max(closes[-3:]) > r * 1.003 and closes[-1] <= r * 1.003:
            ax.annotate("Retest / rejection", (x[-1], closes[-1]), xytext=(-90, -45), textcoords="offset points", arrowprops={"arrowstyle": "->", "color": "#ff8a8a"}, color="#ffaaaa", fontsize=9)

    last, first = closes[-1], float(candles[0]["open"])
    move = ((last - first) / first * 100) if first else 0
    ax.set_title(f"{title}\n{symbol} • real Binance 1H OHLCV • {move:+.2f}% displayed", loc="left", fontsize=16, fontweight="bold", color="#f5f7fa", pad=12)
    ax.set_ylabel("Price (USDT)", color="#b9c2cf")
    vol.set_ylabel("Vol", color="#b9c2cf")
    vol.set_xlabel("UTC", color="#b9c2cf")
    ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor="#d8dee7")
    for axis in (ax, vol):
        axis.grid(True, alpha=0.12)
        axis.tick_params(colors="#b9c2cf", labelsize=9)
        for spine in axis.spines.values(): spine.set_color("#303945")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    ax.tick_params(axis="x", labelbottom=False)
    vol.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=8))
    vol.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    fig.text(0.07, 0.025, "Source: Binance Spot public market data • technical markings are observations, not trading advice", fontsize=8.5, color="#8e99a8")
    fig.savefig(output, dpi=190, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
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
    title = plan.get("title") or "Market structure"
    output = VISUAL_DIR / (report_path.stem + ".png")
    if chart_type == "candlestick_chart":
        requested = [str(x.get("symbol", "")).upper() for x in plan.get("data_points", []) if isinstance(x, dict)]
        selected = next((s for s in signals if s.get("symbol", "").upper() in requested and s.get("candles_1h")), None)
        selected = selected or next((s for s in signals if s.get("candles_1h")), None)
        if not selected:
            print(json.dumps({"status": "VISUAL_SKIPPED_NO_REAL_CANDLES", "report": str(report_path)} , indent=2))
            return
        render_candlestick(selected["symbol"], selected["candles_1h"], title, output, plan.get("technical_annotations"))
    elif chart_type in {"market_bar_chart", "market_comparison"}:
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        values = [float(x.get("price_change_percent", 0)) for x in data]
        plt.figure(figsize=(12, 7), facecolor="#10151c")
        ax = plt.gca(); ax.set_facecolor("#151b23")
        ax.bar(labels, values); ax.axhline(0, linewidth=1, color="#8e99a8")
        ax.set_title(title, color="#f5f7fa"); ax.set_ylabel("24h price change (%)", color="#b9c2cf")
        ax.tick_params(colors="#b9c2cf"); plt.xticks(rotation=35, ha="right"); plt.tight_layout(); plt.savefig(output, dpi=190, bbox_inches="tight"); plt.close()
    elif chart_type == "market_range_chart":
        data = signals[:6]; labels = [str(x.get("symbol", "?")) for x in data]
        lows, highs, centers = [], [], []
        for item in data:
            candles = item.get("candles_1h") or []
            lows.append(min(float(c["low"]) for c in candles) if candles else float(item.get("last_price", 0)))
            highs.append(max(float(c["high"]) for c in candles) if candles else float(item.get("last_price", 0)))
            centers.append(float(candles[-1]["close"]) if candles else float(item.get("last_price", 0)))
        plt.figure(figsize=(12, 7)); plt.vlines(range(len(labels)), lows, highs, linewidth=3); plt.scatter(range(len(labels)), centers); plt.xticks(range(len(labels)), labels, rotation=35, ha="right"); plt.title(title); plt.ylabel("Observed price range (USDT)"); plt.tight_layout(); plt.savefig(output, dpi=190, bbox_inches="tight"); plt.close()
    else:
        plt.figure(figsize=(12, 7)); plt.axis("off"); plt.text(0.05, 0.88, title, fontsize=20, va="top", wrap=True); plt.text(0.05, 0.72, plan.get("caption") or plan.get("purpose") or title, fontsize=13, va="top", wrap=True); plt.tight_layout(); plt.savefig(output, dpi=190, bbox_inches="tight"); plt.close()
    print(json.dumps({"status": "VISUAL_CREATED", "type": chart_type, "output": str(output), "caption": plan.get("caption", ""), "alt_text": plan.get("alt_text", ""), "patterns_detected": detect_patterns(selected["candles_1h"]) if chart_type == "candlestick_chart" else []}, indent=2))


if __name__ == "__main__":
    main()
