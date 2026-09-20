"""Render an immutable historical Signal-First setup chart.

No live chart service is consulted. The image is drawn exclusively from
data/live/historical_setup_snapshot.json so candles cannot move after publication.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/live/historical_setup_snapshot.json"
OUT = ROOT / "data/live/visual.png"
META = ROOT / "data/live/visual_metadata.json"

W, H = 1800, 1000
LEFT, RIGHT, TOP, BOTTOM = 120, 80, 150, 170
CHART_H = 610
VOL_TOP = TOP + CHART_H + 35
VOL_H = 80


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fmt(v):
    if v is None:
        return "n/a"
    x = float(v)
    if abs(x) >= 100:
        return f"{x:.2f}"
    if abs(x) >= 1:
        return f"{x:.4f}"
    if abs(x) >= 0.01:
        return f"{x:.6f}"
    return f"{x:.8f}"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    if not SNAPSHOT.exists():
        raise SystemExit("historical setup snapshot missing")
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if snap.get("status") != "FROZEN" or snap.get("lookahead_protection") is not True:
        raise SystemExit("historical snapshot is not frozen/lookahead protected")

    candles = snap.get("candles_1h") or []
    if len(candles) < 3:
        raise SystemExit("historical snapshot has too few candles")
    candles = candles[-36:]

    pred = snap.get("prediction") or {}
    symbol = str(snap.get("symbol") or "").upper()
    side = str(pred.get("direction") or "").upper()
    signal_price = float(snap.get("signal_price"))
    entry = pred.get("entry_trigger")
    tp1 = pred.get("tp1")
    tp2 = pred.get("tp2")
    sl = pred.get("sl")
    created = str(snap.get("signal_created_at") or "")
    cutoff = str(snap.get("data_cutoff") or created)

    vals = [float(c["high"]) for c in candles] + [float(c["low"]) for c in candles]
    for x in (signal_price, entry, tp1, tp2, sl):
        if x is not None:
            vals.append(float(x))
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.08, abs(hi) * 0.003, 1e-12)
    lo -= pad
    hi += pad

    img = Image.new("RGB", (W, H), "#10141c")
    d = ImageDraw.Draw(img)
    title = font(40, True)
    sub = font(22)
    label = font(20, True)
    small = font(17)

    d.text((LEFT, 34), f"{symbol} • 1H HISTORICAL SIGNAL SNAPSHOT", font=title, fill="#f2f4f7")
    d.text((LEFT, 88), f"Signal created {created}  |  Data cutoff {cutoff}  |  Completed candles only", font=sub, fill="#aeb6c2")
    d.text((W-470, 45), f"{side} CONDITIONAL SETUP", font=label, fill="#f2f4f7")

    x0, x1 = LEFT, W - RIGHT
    y0, y1 = TOP, TOP + CHART_H

    # Grid and y-axis.
    for i in range(6):
        y = y0 + i * CHART_H / 5
        d.line((x0, y, x1, y), fill="#29313d", width=1)
        val = hi - (hi - lo) * i / 5
        d.text((18, y - 10), fmt(val), font=small, fill="#8e98a7")

    n = len(candles)
    step = (x1 - x0) / n
    body_w = max(6, int(step * 0.52))

    def py(v):
        return y1 - (float(v) - lo) / (hi - lo) * CHART_H

    max_vol = max(float(c.get("volume", 0)) for c in candles) or 1.0

    for i, c in enumerate(candles):
        cx = x0 + (i + 0.5) * step
        yo, yc = py(c["open"]), py(c["close"])
        yh, yl = py(c["high"]), py(c["low"])
        up = float(c["close"]) >= float(c["open"])
        candle_fill = "#48d597" if up else "#ef6671"
        d.line((cx, yh, cx, yl), fill=candle_fill, width=3)
        topb, botb = sorted((yo, yc))
        d.rectangle((cx - body_w/2, topb, cx + body_w/2, max(botb, topb + 2)), fill=candle_fill)
        vh = float(c.get("volume", 0)) / max_vol * VOL_H
        d.rectangle((cx - body_w/2, VOL_TOP + VOL_H - vh, cx + body_w/2, VOL_TOP + VOL_H), fill="#465262")

    # Setup lines.
    levels = [
        ("SIGNAL PRICE", signal_price, "#d7dce3", 3),
        ("ENTRY", entry, "#62a8ff", 3),
        ("TP1", tp1, "#49d597", 3),
        ("TP2", tp2, "#49d597", 2),
        ("SL / INVALIDATION", sl, "#ef6671", 3),
    ]
    for name, value, stroke, width in levels:
        if value is None:
            continue
        y = clamp(py(value), y0, y1)
        d.line((x0, y, x1, y), fill=stroke, width=width)
        text = f"{name}  {fmt(value)}"
        tw = d.textbbox((0,0), text, font=small)[2]
        d.rectangle((x1 - tw - 18, y - 13, x1, y + 13), fill="#10141c")
        d.text((x1 - tw - 10, y - 10), text, font=small, fill=stroke)

    d.text((x0, VOL_TOP + VOL_H + 18), "Volume", font=small, fill="#8e98a7")
    if candles:
        first = datetime.fromtimestamp(int(candles[0]["open_time"]) / 1000, tz=timezone.utc).strftime("%d %b %H:%M")
        last = datetime.fromtimestamp(int(candles[-1]["open_time"]) / 1000, tz=timezone.utc).strftime("%d %b %H:%M")
        d.text((x0, VOL_TOP + VOL_H + 48), first, font=small, fill="#8e98a7")
        d.text((x1-150, VOL_TOP + VOL_H + 48), last, font=small, fill="#8e98a7")

    d.text((LEFT, H-55), "Historical setup • no post-signal candles used • outcome is evaluated separately", font=small, fill="#aeb6c2")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    meta = {
        "status": "HISTORICAL_SNAPSHOT_CREATED",
        "provider": "Local historical OHLCV renderer",
        "base_symbol": symbol,
        "tradingview_symbol": None,
        "market_type": "BINANCE_HISTORICAL_OHLCV",
        "timeframe": "1H",
        "signal_created_at": created,
        "data_cutoff": cutoff,
        "candle_count": len(candles),
        "candle_policy": "completed_candles_only",
        "lookahead_protection": True,
        "report_file": None,
        "prediction_markings": {"direction": side, "entry_trigger": entry, "tp1": tp1, "tp2": tp2, "sl": sl, "signal_price": signal_price},
        "output": str(OUT),
        "bytes": OUT.stat().st_size,
    }
    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
