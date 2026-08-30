"""Validate that the TradingView screenshot is real, non-blank, and not an invalid-symbol page."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path


def image_validate(path: str) -> int:
    p = Path(path)
    if not p.exists() or p.stat().st_size < 10_000:
        print(f"TRADINGVIEW_INVALID: missing_or_too_small:{p}")
        return 1
    try:
        from PIL import Image, ImageStat
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if w < 600 or h < 300:
            print(f"TRADINGVIEW_INVALID: dimensions:{w}x{h}")
            return 1
        stat = ImageStat.Stat(im)
        spread = sum(hi - lo for lo, hi in stat.extrema) / 3
        variance = sum(stat.stddev) / 3
        if spread < 12 or variance < 5:
            print(f"TRADINGVIEW_INVALID: blank_or_uniform:spread={spread:.2f},std={variance:.2f}")
            return 1
        white = sum(1 for px in im.resize((120, 80)).getdata() if min(px) > 245)
        ratio = white / (120 * 80)
        if ratio > .94:
            print(f"TRADINGVIEW_INVALID: mostly_white:{ratio:.3f}")
            return 1
        print(f"TRADINGVIEW_VALID_IMAGE: {p} {w}x{h} size={p.stat().st_size} spread={spread:.2f} std={variance:.2f} white={ratio:.3f}")
        return 0
    except Exception as e:
        print(f"TRADINGVIEW_INVALID: image_validation_error:{type(e).__name__}:{e}")
        return 1


def browser_validate(html_path: str = "data/live/tradingview_capture.html") -> int:
    """Open the exact capture HTML and inspect every frame for TradingView failure text."""
    p = Path(html_path)
    if not p.exists():
        print(f"TRADINGVIEW_INVALID: capture_html_missing:{p}")
        return 1

    script = r'''
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true,args:['--disable-blink-features=AutomationControlled','--disable-dev-shm-usage']});
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  try {
    await page.goto('file://' + require('path').resolve(process.argv[1]), {waitUntil:'domcontentloaded', timeout:30000});
    await page.waitForSelector('iframe', {timeout:30000});
    await page.waitForTimeout(12000);
    const frames = page.frames().map(f => ({url:f.url(), text:(f.url().includes('tradingview') ? (f.locator('body').innerText().catch(()=>'')) : Promise.resolve('')})));
    const resolved = [];
    for (const item of frames) resolved.push({url:item.url, text:(await item.text).slice(0,12000)});
    const bad = resolved.filter(x => /this symbol doesn't exist|symbol doesn't exist|change symbol/i.test(x.text));
    const usable = resolved.filter(x => /TradingView|chart|price|volume|open|high|low|close/i.test(x.text));
    console.log(JSON.stringify({frame_count:resolved.length,bad_frames:bad.map(x=>x.url),usable_frames:usable.map(x=>x.url)}));
    if (bad.length) process.exitCode=2;
    else if (!usable.length) process.exitCode=3;
  } finally { await browser.close(); }
})().catch(e => { console.error(e.stack || e); process.exit(4); });
'''
    try:
        result = subprocess.run(
            ["node", "-e", script, str(p.resolve())],
            text=True,
            capture_output=True,
            timeout=50,
        )
    except Exception as e:
        print(f"TRADINGVIEW_INVALID: browser_validation_error:{type(e).__name__}:{e}")
        return 1

    if result.stdout.strip():
        print(f"TRADINGVIEW_BROWSER: {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"TRADINGVIEW_BROWSER_STDERR: {result.stderr.strip()}")
    if result.returncode == 2:
        print("TRADINGVIEW_INVALID: TradingView reported that the selected symbol does not exist")
        return 1
    if result.returncode != 0:
        print(f"TRADINGVIEW_INVALID: browser_frame_check_failed:rc={result.returncode}")
        return 1
    return 0


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/live/visual.png"
    rc = image_validate(path)
    if rc:
        return rc
    return browser_validate()


if __name__ == "__main__":
    raise SystemExit(main())
