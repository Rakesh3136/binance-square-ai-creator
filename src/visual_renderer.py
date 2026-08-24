import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

REPORT_DIR = Path("data/reports")
VISUAL_DIR = Path("data/visuals")
LIVE_VISUAL = Path("data/live/visual.png")
VISUAL_DIR.mkdir(parents=True, exist_ok=True)
LIVE_VISUAL.parent.mkdir(parents=True, exist_ok=True)


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


def pivot_levels(candles, lookback=2):
    highs, lows = [], []
    for i in range(lookback, len(candles) - lookback):
        h = float(candles[i]["high"]); l = float(candles[i]["low"])
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
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b[0] - a[0] >= 3:
            midpoint = max(closes[a[0]:b[0] + 1])
            if abs(a[1] - b[1]) / max((a[1] + b[1]) / 2, 1e-12) < .035 and midpoint > max(a[1], b[1]) * 1.02:
                patterns.append("double_bottom_W")
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b[0] - a[0] >= 3:
            valley = min(closes[a[0]:b[0] + 1])
            if abs(a[1] - b[1]) / max((a[1] + b[1]) / 2, 1e-12) < .035 and valley < min(a[1], b[1]) * .98:
                patterns.append("double_top_M")
    if len(recent) >= 12:
        left, middle, right = max(recent[:4]), min(recent[4:10]), max(recent[-4:])
        if middle < left * .94 and right > left * .96 and right < left * 1.04:
            patterns.append("cup_and_handle")
    return patterns


def render_candlestick(symbol, candles, title, output):
    if len(candles) < 8:
        raise RuntimeError(f"Not enough real 1h candles for {symbol}")
    times = [datetime.fromtimestamp(c["open_time"] / 1000, tz=timezone.utc) for c in candles]
    x = mdates.date2num(times)
    closes = [float(c["close"]) for c in candles]
    width = max((x[-1] - x[0]) / len(x) * .62, .012)
    fig = plt.figure(figsize=(12, 8), facecolor="#0f141b")
    ax = fig.add_axes([.07, .20, .90, .67], facecolor="#141a22")
    vol = fig.add_axes([.07, .08, .90, .10], sharex=ax, facecolor="#141a22")
    for t, c in zip(x, candles):
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        color = "#22c99a" if cl >= o else "#ff5b62"
        ax.vlines(t, l, h, color=color, linewidth=1.1)
        ax.add_patch(Rectangle((t-width/2, min(o, cl)), width, max(abs(cl-o), max(abs(cl), 1e-12)*.00005), facecolor=color, edgecolor=color, linewidth=.7))
        vol.bar(t, float(c["volume"]), width=width, color=color, alpha=.45)
    ax.plot(x, ema(closes, 9), color="#f2b84b", linewidth=1.1, label="EMA 9")
    ax.plot(x, ema(closes, 20), color="#8da7ff", linewidth=1.1, label="EMA 20")
    swing_highs, swing_lows = pivot_levels(candles, 2)
    if swing_highs: ax.axhline(swing_highs[-1][1], color="#ff8a8a", linestyle="--", linewidth=1)
    if swing_lows: ax.axhline(swing_lows[-1][1], color="#7fe0bb", linestyle="--", linewidth=1)
    patterns = detect_patterns(candles)
    if patterns: ax.text(.01, .03, "Detected: " + ", ".join(patterns), transform=ax.transAxes, color="#ffcf66", fontsize=9)
    first = float(candles[0]["open"]); last = closes[-1]; move = ((last-first)/first*100) if first else 0
    ax.set_title(f"{title}\n{symbol} • real Binance 1H OHLCV • {move:+.2f}%", loc="left", fontsize=16, fontweight="bold", color="#f5f7fa")
    ax.set_ylabel("Price (USDT)"); vol.set_ylabel("Vol"); vol.set_xlabel("UTC")
    ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor="#d8dee7")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc)); ax.tick_params(axis="x", labelbottom=False)
    vol.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=8)); vol.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=timezone.utc))
    fig.text(.07, .025, "Source: Binance Spot public market data • observations, not trading advice", fontsize=8.5, color="#8e99a8")
    fig.savefig(output, dpi=190, bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)


def main():
    report_path = latest_report()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    market = report.get("live_market_snapshot") or {}
    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status":"NO_VISUAL_REQUESTED","report":str(report_path)})); return 0
    signals = market.get("top_content_signals") or []
    if not signals:
        print(json.dumps({"status":"NO_MARKET_DATA_FOR_VISUAL","report":str(report_path)})); return 0
    output = VISUAL_DIR / (report_path.stem + ".png")
    chart_type = plan.get("type")
    if chart_type == "candlestick_chart":
        requested = [str(x.get("symbol","")).upper() for x in plan.get("data_points",[]) if isinstance(x,dict)]
        selected = next((s for s in signals if str(s.get("symbol","")).upper() in requested and s.get("candles_1h")), None)
        selected = selected or next((s for s in signals if s.get("candles_1h")), None)
        if not selected:
            print(json.dumps({"status":"VISUAL_SKIPPED_NO_REAL_CANDLES","report":str(report_path)})); return 0
        render_candlestick(selected["symbol"], selected["candles_1h"], plan.get("title") or "Market structure", output)
    else:
        data = signals[:6]; labels=[str(x.get("symbol","?")) for x in data]; values=[float(x.get("price_change_percent",0)) for x in data]
        plt.figure(figsize=(12,7)); plt.bar(labels, values); plt.axhline(0, linewidth=1); plt.xticks(rotation=35, ha="right"); plt.title(plan.get("title") or "Market comparison"); plt.tight_layout(); plt.savefig(output, dpi=190, bbox_inches="tight"); plt.close()
    shutil.copy2(output, LIVE_VISUAL)
    print(json.dumps({"status":"VISUAL_CREATED","type":chart_type,"output":str(output),"publish_output":str(LIVE_VISUAL),"patterns_detected":detect_patterns(selected["candles_1h"]) if chart_type == "candlestick_chart" else []}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())