"""Validate that the TradingView screenshot is real, non-blank, and not an invalid-symbol page."""
from __future__ import annotations
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
        small = im.resize((120, 80))
        white = sum(1 for px in small.getdata() if min(px) > 245)
        ratio = white / (120 * 80)
        if ratio > 0.94:
            print(f"TRADINGVIEW_INVALID: mostly_white:{ratio:.3f}")
            return 1
        print(f"TRADINGVIEW_VALID_IMAGE: {p} {w}x{h} size={p.stat().st_size} spread={spread:.2f} std={variance:.2f} white={ratio:.3f}")
        return 0
    except Exception as e:
        print(f"TRADINGVIEW_INVALID: image_validation_error:{type(e).__name__}:{e}")
        return 1


def browser_validate(html_path: str = "data/live/tradingview_capture.html") -> int:
    """Open the exact capture HTML and reject an actual TradingView invalid-symbol page.

    Keep the Playwright JavaScript deliberately simple. The previous implementation used
    a nested ternary/promise expression that caused Node to fail parsing the validator,
    which blocked every publication even when the chart image itself was valid.
    """
    p = Path(html_path)
    if not p.exists():
        print(f"TRADINGVIEW_INVALID: capture_html_missing:{p}")
        return 1

    script = r'''
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    const filePath = path.resolve(process.argv[1]);
    await page.goto('file://' + filePath, {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    await page.waitForSelector('iframe', { timeout: 30000 });
    await page.waitForTimeout(8000);

    const resolved = [];
    for (const frame of page.frames()) {
      let text = '';
      try {
        text = await frame.locator('body').innerText({ timeout: 3000 });
      } catch (_) {
        // Some cross-origin TradingView frames do not expose body text.
        // The screenshot validator below remains authoritative for image quality.
      }
      resolved.push({
        url: frame.url(),
        text: String(text || '').slice(0, 12000)
      });
    }

    const badPattern = /this symbol doesn't exist|symbol doesn't exist|change symbol/i;
    const badFrames = resolved.filter(item => badPattern.test(item.text));

    console.log(JSON.stringify({
      frame_count: resolved.length,
      bad_frames: badFrames.map(item => item.url)
    }));

    if (badFrames.length > 0) {
      process.exitCode = 2;
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(4);
});
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

    # Validation is shared by all visual lanes. Signal-First technical
    # charts may use the local historical renderer, while meme/editorial
    # visuals intentionally do not create TradingView HTML. After the image
    # quality checks above, only the actual TradingView lane needs browser
    # validation.
    metadata = Path("data/live/visual_metadata.json")
    if metadata.exists():
        try:
            import json
            meta = json.loads(metadata.read_text(encoding="utf-8"))
            provider = str(meta.get("provider") or "")
            status = str(meta.get("status") or "")
            visual_type = str(meta.get("visual_type") or "").lower()

            if provider == "Local historical OHLCV renderer" and status == "HISTORICAL_SNAPSHOT_CREATED":
                print("TRADINGVIEW_FALLBACK_VALID: local historical OHLCV renderer")
                return 0

            non_tradingview_types = {
                "meme", "crypto_meme", "real_world_photo_meme",
                "editorial", "news", "infographic", "education",
            }
            if visual_type in non_tradingview_types or (
                provider and provider not in {"TradingView", "Local historical OHLCV renderer"}
            ):
                print(f"NON_TRADINGVIEW_VISUAL_VALID: provider={provider or '<unknown>'} type={visual_type or '<unknown>'}")
                return 0
        except Exception as e:
            print(f"TRADINGVIEW_METADATA_WARNING: {type(e).__name__}:{e}")

    return browser_validate()


if __name__ == "__main__":
    raise SystemExit(main())
