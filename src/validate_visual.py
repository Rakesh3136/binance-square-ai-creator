from __future__ import annotations

import json
import re
from pathlib import Path

REPORT_DIR = Path("data/reports")
META = Path("data/live/visual_metadata.json")
VISUAL = Path("data/live/visual.png")


def latest_report() -> Path:
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit("No fresh multi-agent report found")
    return reports[0]


def tickers(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\$?([A-Z0-9]{2,12})USDT\b", text.upper())))


def main() -> None:
    report = json.loads(latest_report().read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status": "VISUAL_NOT_REQUESTED"}))
        return

    if not META.exists() or not VISUAL.exists():
        raise SystemExit("TradingView visual metadata/image missing")

    meta = json.loads(META.read_text(encoding="utf-8"))
    if meta.get("provider") != "TradingView" or meta.get("status") != "TRADINGVIEW_CREATED":
        raise SystemExit("Visual is not a verified TradingView snapshot")

    post = str((report.get("draft") or {}).get("post") or (report.get("draft") or {}).get("text") or "")
    post_tickers = tickers(post)
    base = str(meta.get("base_symbol") or "").upper()
    if not base or base not in post_tickers:
        raise SystemExit(f"TradingView chart symbol {base or '<missing>'} does not match post tickers {post_tickers}")

    if not str(meta.get("tradingview_symbol", "")).startswith("BINANCE:"):
        raise SystemExit("TradingView symbol is not a Binance market symbol")

    if VISUAL.stat().st_size < 20_000:
        raise SystemExit("TradingView image is suspiciously small")

    print(json.dumps({
        "status": "VISUAL_MATCH_CONFIRMED",
        "provider": "TradingView",
        "symbol": meta["tradingview_symbol"],
        "post_tickers": post_tickers,
        "image_bytes": VISUAL.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
