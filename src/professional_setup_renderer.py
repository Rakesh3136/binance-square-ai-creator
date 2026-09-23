"""Analyst-style mobile Binance Square setup chart.

The renderer is presentation-only: every price and candle comes from the frozen
historical snapshot. It deliberately avoids dashboard-like cards and instead
uses a chart-first composition with subtle context, volume, recent-range
markers and one clear decision level.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data/live/historical_setup_snapshot.json"
OUT = ROOT / "data/live/visual.png"
META = ROOT / "data/live/visual_metadata.json"
W, H = 1080, 1350

BG = "#080c11"
PANEL = "#0d131a"
GRID = "#18222c"
TEXT = "#f4f7fa"
MUTED = "#7f8b98"
LONG = "#35d58a"
SHORT = "#ff6372"
ENTRY = "#f2bd55"
BLUE = "#69a7ff"


def font(size: int, bold: bool = False):
    name = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(name, size) if Path(name).exists() else ImageFont.load_default()


def num(v):
    try:
        return float(v)
    except Exception:
        return None


def fmt(v):
    x = num(v)
    if x is None:
        return "—"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 100:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:,.4f}".rstrip("0").rstrip(".")
    if abs(x) >= 0.01:
        return f"{x:.6f}".rstrip("0").rstrip(".")
    return f"{x:.8f}".rstrip("0").rstrip(".")


def pct(a, b):
    if a in (None, 0) or b is None:
        return None
    return (b / a - 1.0) * 100.0


def text_box(draw, xy, text, f, fill=TEXT, pad=8, outline=None):
    x, y = xy
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.rounded_rectangle((x, y, x + tw + pad * 2, y + th + pad * 2), radius=8, fill=BG, outline=outline, width=1 if outline else 0)
    draw.text((x + pad, y + pad - 2), text, font=f, fill=fill)
    return tw + pad * 2, th + pad * 2


def dashed(draw, x1, y, x2, fill, width=2, dash=11, gap=8):
    x = int(x1)
    x2 = int(x2)
    while x < x2:
        draw.line((x, y, min(x + dash, x2), y), fill=fill, width=width)
        x += dash + gap


def main():
    snapshot = json.loads(SNAP.read_text(encoding="utf-8"))
    if snapshot.get("status") != "FROZEN" or snapshot.get("lookahead_protection") is not True:
        raise SystemExit("snapshot is not frozen")

    candles = snapshot.get("candles_1h") or []
    if len(candles) < 8:
        raise SystemExit("too few historical candles")
    candles = candles[-48:]
    prediction = snapshot.get("prediction") or {}
    side = str(prediction.get("direction") or "").upper()
    symbol = str(snapshot.get("symbol") or "").upper()
    signal = num(snapshot.get("signal_price"))
    entry = num(prediction.get("entry_trigger"))
    tp1 = num(prediction.get("tp1"))
    tp2 = num(prediction.get("tp2"))
    sl = num(prediction.get("sl"))
    confidence = num(prediction.get("confidence"))

    if side not in {"LONG", "SHORT"} or any(x is None for x in (signal, entry, tp1, tp2, sl)):
        raise SystemExit("frozen prediction contract incomplete")

    closes = [num(c.get("close")) for c in candles]
    highs = [num(c.get("high")) for c in candles]
    lows = [num(c.get("low")) for c in candles]
    volumes = [num(c.get("volume")) or 0 for c in candles]
    last = closes[-1]
    prior = closes[-2]
    move_6 = pct(closes[-7], last) if len(closes) >= 7 else None
    recent_hi = max(x for x in highs[-8:] if x is not None)
    recent_lo = min(x for x in lows[-8:] if x is not None)
    max_vol = max(volumes) if volumes else 0

    values = [x for x in highs + lows + [signal, entry, tp1, tp2, sl] if x is not None]
    lo, hi = min(values), max(values)
    pad = max((hi - lo) * 0.07, abs(hi) * 0.002, 1e-12)
    lo -= pad
    hi += pad

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    title = font(43, True)
    big = font(29, True)
    medium = font(23, True)
    body = font(21)
    small = font(17)
    tiny = font(14)

    # Header: one human-readable focal line, not a dashboard header.
    draw.text((58, 38), f"${symbol}", font=title, fill=TEXT)
    badge = "LONG" if side == "LONG" else "SHORT"
    badge_color = LONG if side == "LONG" else SHORT
    bb = draw.textbbox((0, 0), badge, font=medium)
    bx = W - 58 - (bb[2] - bb[0]) - 28
    draw.rounded_rectangle((bx, 40, W - 58, 84), radius=12, fill="#14211d" if side == "LONG" else "26161b")
    draw.text((bx + 14, 48), badge, font=medium, fill=badge_color)

    draw.text((58, 94), "1H decision map", font=medium, fill=TEXT)
    if move_6 is not None:
        move_text = f"6-candle move {move_6:+.1f}%"
    else:
        move_text = "completed candles only"
    draw.text((58, 130), f"Decision level {fmt(entry)}  •  {move_text}", font=small, fill=MUTED)

    # Main chart panel.
    chart_l, chart_r = 58, 1022
    chart_t, chart_b = 185, 935
    vol_t, vol_b = 960, 1090
    chart_h = chart_b - chart_t
    chart_w = chart_r - chart_l

    draw.rounded_rectangle((chart_l, chart_t, chart_r, vol_b), radius=18, fill=PANEL, outline="#202c38", width=1)

    def py(value):
        return chart_b - (float(value) - lo) / (hi - lo) * chart_h

    # Quiet price grid.
    for i in range(6):
        y = chart_t + i * chart_h / 5
        value = hi - (hi - lo) * i / 5
        draw.line((chart_l + 18, y, chart_r - 18, y), fill=GRID, width=1)
        draw.text((chart_r - 110, y - 9), fmt(value), font=tiny, fill=MUTED)

    # Recent-range shading. This is derived directly from the last 8 candles.
    rhi, rlo = py(recent_hi), py(recent_lo)
    draw.rectangle((chart_l + 18, min(rhi, rlo), chart_r - 18, max(rhi, rlo)), fill="#111a22")
    draw.text((chart_l + 28, min(rhi, rlo) + 10), "RECENT 8H RANGE", font=tiny, fill="#526273")

    # Candles.
    n = len(candles)
    step = (chart_w - 44) / n
    candle_w = max(7, int(step * 0.54))
    for i, c in enumerate(candles):
        o, h, l, cl = [num(c.get(k)) for k in ("open", "high", "low", "close")]
        if None in (o, h, l, cl):
            continue
        cx = chart_l + 22 + (i + 0.5) * step
        yo, yh, yl, yc = py(o), py(h), py(l), py(cl)
        rising = cl >= o
        col = LONG if rising else SHORT
        draw.line((cx, yh, cx, yl), fill=col, width=3)
        top, bottom = sorted((yo, yc))
        draw.rounded_rectangle((cx - candle_w / 2, top, cx + candle_w / 2, max(bottom, top + 3)), radius=2, fill=col)

    # Volume pane: real snapshot volume, visually subordinate to price.
    draw.text((chart_l + 22, vol_t + 6), "VOLUME", font=tiny, fill=MUTED)
    for i, c in enumerate(candles):
        v = num(c.get("volume")) or 0
        cx = chart_l + 22 + (i + 0.5) * step
        bar_h = 88 * (v / max_vol) if max_vol else 0
        rising = num(c.get("close")) >= num(c.get("open"))
        col = LONG if rising else SHORT
        draw.rectangle((cx - candle_w / 2, vol_b - bar_h, cx + candle_w / 2, vol_b), fill=col)

    # Decision and target levels: sparse, thin, analyst-like.
    level_specs = [
        ("TP2", tp2, BLUE),
        ("TP1", tp1, LONG),
        ("DECISION", entry, ENTRY),
        ("INVALID", sl, SHORT),
    ]
    for label, value, col in level_specs:
        y = py(value)
        if chart_t <= y <= chart_b:
            dashed(draw, chart_l + 22, y, chart_r - 122, col, width=2 if label != "DECISION" else 3)
            text_box(draw, (chart_r - 112, max(chart_t + 6, min(chart_b - 30, y - 15))), f"{label} {fmt(value)}", tiny, fill=col, outline=col)

    # Current snapshot marker: small, never a giant arrow.
    sy = py(signal)
    if chart_t <= sy <= chart_b:
        draw.ellipse((chart_l + 22, sy - 5, chart_l + 32, sy + 5), fill=TEXT)
        draw.text((chart_l + 40, sy - 10), f"snapshot {fmt(signal)}", font=tiny, fill=TEXT)

    # Human-style annotation: one question, one decision, no template dump.
    decision_distance = pct(last, entry)
    if side == "LONG":
        sentence = f"Watching whether 1H can reclaim {fmt(entry)} with follow-through."
    else:
        sentence = f"Watching whether 1H rejects {fmt(entry)} with follow-through."
    draw.text((58, 1122), sentence, font=body, fill=TEXT)
    if decision_distance is not None:
        relation = f"Current snapshot is {abs(decision_distance):.1f}% {'below' if decision_distance < 0 else 'above'} the decision level."
    else:
        relation = "Decision level is taken directly from the frozen contract."
    draw.text((58, 1160), relation, font=small, fill=MUTED)

    # Compact trade strip, intentionally not four giant cards.
    strip_y = 1200
    items = [("ENTRY", entry, ENTRY), ("TP1", tp1, LONG), ("TP2", tp2, LONG), ("SL", sl, SHORT)]
    col_w = (chart_r - chart_l) / 4
    for i, (label, value, col) in enumerate(items):
        x = chart_l + i * col_w
        draw.text((x, strip_y), label, font=tiny, fill=col)
        draw.text((x, strip_y + 25), fmt(value), font=medium, fill=TEXT)

    risk = abs(entry - sl)
    reward = abs(tp2 - entry)
    rr = reward / risk if risk else None
    footer = "Conditional setup • no guarantee"
    if rr is not None:
        footer += f"  •  R:R {rr:.2f}"
    if confidence is not None:
        footer += f"  •  contract confidence {confidence:.0f}%"
    draw.text((58, 1285), footer, font=tiny, fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)

    metadata = {
        "status": "HISTORICAL_SNAPSHOT_CREATED",
        "provider": "Local historical OHLCV renderer",
        "renderer": "professional_setup_renderer_v5_analyst_square_portrait",
        "base_symbol": symbol,
        "market_type": "BINANCE_HISTORICAL_OHLCV",
        "timeframe": "1H",
        "signal_created_at": snapshot.get("signal_created_at"),
        "data_cutoff": snapshot.get("data_cutoff"),
        "candle_count": len(candles),
        "candle_policy": "completed_candles_only",
        "lookahead_protection": True,
        "visual_style": "analyst_chart_first_mobile_square",
        "derived_context": {"recent_candle_window": 8, "recent_high": recent_hi, "recent_low": recent_lo, "last_close": last, "previous_close": prior, "six_candle_move_pct": move_6},
        "prediction_markings": {"direction": side, "entry_trigger": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "signal_price": signal, "confidence": confidence, "risk_reward": rr},
        "output": str(OUT),
        "bytes": OUT.stat().st_size,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    META.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
