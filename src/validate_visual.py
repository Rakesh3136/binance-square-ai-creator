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
    """Extract real cashtags/USDT pairs without treating $150 or $77 as tickers.

    Binance/TradingView supports one-character symbols (for example T), so the
    first character must be a letter but the total symbol length may be 1.
    """
    upper = text.upper()
    found = re.findall(r"\$([A-Z][A-Z0-9]{0,11})(?:USDT)?\b", upper)
    found += re.findall(r"\b([A-Z][A-Z0-9]{0,11})USDT\b", upper)
    return list(dict.fromkeys(found))


def main() -> None:
    if not META.exists() or not VISUAL.exists():
        raise SystemExit("TradingView visual metadata/image missing")

    meta = json.loads(META.read_text(encoding="utf-8"))
    if meta.get("provider") != "TradingView" or meta.get("status") != "TRADINGVIEW_CREATED":
        raise SystemExit("Visual is not a verified TradingView snapshot")

    # The renderer records the exact report it used. This prevents a later
    # report write from racing the validator and falsely reporting a symbol mismatch.
    report_name = str(meta.get("report_file") or "")
    report_path = REPORT_DIR / report_name if report_name else latest_report()
    if not report_path.exists():
        raise SystemExit(f"TradingView source report missing: {report_name or '<latest>'}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status": "VISUAL_NOT_REQUESTED"}))
        return

    post = str((report.get("draft") or {}).get("post") or (report.get("draft") or {}).get("text") or "")
    post_tickers = tickers(post)
    base = str(meta.get("base_symbol") or "").upper()
    if not base or base not in post_tickers:
        raise SystemExit(f"TradingView chart symbol {base or '<missing>'} does not match post tickers {post_tickers}")

    tv_symbol = str(meta.get("tradingview_symbol", ""))
    if base not in {str(x).upper() for x in meta.get("post_tickers", [])}:
        raise SystemExit(f"TradingView metadata tickers do not contain rendered symbol {base}")
    if not tv_symbol.startswith("BINANCE:"):
        raise SystemExit("TradingView symbol is not a Binance market symbol")
    if VISUAL.stat().st_size < 20_000:
        raise SystemExit("TradingView image is suspiciously small")

    print(json.dumps({
        "status": "VISUAL_MATCH_CONFIRMED",
        "provider": "TradingView",
        "symbol": tv_symbol,
        "post_tickers": post_tickers,
        "report_file": report_path.name,
        "image_bytes": VISUAL.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
