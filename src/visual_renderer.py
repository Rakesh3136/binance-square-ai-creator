"""TradingView-backed visual renderer for Binance Square."""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("tradingview_renderer.mjs")


def main() -> int:
    if not SCRIPT.exists():
        raise SystemExit(f"Missing TradingView renderer: {SCRIPT}")
    return subprocess.run(["node", str(SCRIPT)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
