"""Reject blank or obviously invalid TradingView assets before publication."""
from __future__ import annotations
import sys
from pathlib import Path

def validate(path: str) -> int:
    p=Path(path)
    if not p.exists() or p.stat().st_size < 10_000:
        print(f"TRADINGVIEW_INVALID: missing_or_too_small:{p}")
        return 1
    try:
        from PIL import Image, ImageStat
        im=Image.open(p).convert("RGB")
        w,h=im.size
        if w < 600 or h < 300:
            print(f"TRADINGVIEW_INVALID: dimensions:{w}x{h}")
            return 1
        stat=ImageStat.Stat(im)
        means=stat.mean
        extrema=stat.extrema
        # A blank screenshot is typically near-uniform. Require visible pixel variation.
        spread=sum((hi-lo) for lo,hi in extrema)/3
        variance=sum(stat.stddev)/3
        if spread < 12 or variance < 5:
            print(f"TRADINGVIEW_INVALID: blank_or_uniform:spread={spread:.2f},std={variance:.2f}")
            return 1
        # Reject overwhelmingly white images, which commonly indicate a failed page render.
        white=sum(1 for px in im.resize((120,80)).getdata() if min(px) > 245)
        ratio=white/(120*80)
        if ratio > .94:
            print(f"TRADINGVIEW_INVALID: mostly_white:{ratio:.3f}")
            return 1
        print(f"TRADINGVIEW_VALID: {p} {w}x{h} size={p.stat().st_size} spread={spread:.2f} std={variance:.2f} white={ratio:.3f}")
        return 0
    except Exception as e:
        print(f"TRADINGVIEW_INVALID: image_validation_error:{type(e).__name__}:{e}")
        return 1

if __name__=='__main__':
    raise SystemExit(validate(sys.argv[1] if len(sys.argv)>1 else 'data/live/visual.png'))
