from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "data/live/editorial_preflight.json"
ENGAGEMENT = ROOT / "data/live/engagement_strategy.json"
MARKET = ROOT / "data/live/market_snapshot.json"
OUT = ROOT / "data/live/authoritative_opportunity.json"
BINANCE_BASES = [
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
]


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_symbol(value: dict) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("symbol", "selected_lane_symbol", "topic"):
        raw = value.get(key)
        if raw:
            s = str(raw).upper().strip().replace("BINANCE:", "")
            if not s.endswith("USDT"):
                s += "USDT"
            return s
    return ""


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "binance-square-ai-creator/2.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def trading_symbols() -> set[str]:
    last = None
    for base in BINANCE_BASES:
        try:
            data = fetch_json(base + "/api/v3/exchangeInfo?symbolStatus=TRADING")
            return {
                str(x.get("symbol", "")).upper()
                for x in (data.get("symbols") or [])
                if str(x.get("status", "")).upper() == "TRADING"
            }
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Unable to verify Binance trading symbols: {last}")


def candidates(pre: dict, engagement: dict, market: dict) -> list[dict]:
    out: list[dict] = []
    selected = pre.get("selected_opportunity")
    if isinstance(selected, dict):
        out.append(selected)
    selected = engagement.get("selected")
    if isinstance(selected, dict):
        out.append(selected)
    ranked = engagement.get("ranked_candidates")
    if isinstance(ranked, list):
        out.extend(x for x in ranked if isinstance(x, dict))
    for key in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        rows = market.get(key)
        if isinstance(rows, list):
            out.extend(x for x in rows if isinstance(x, dict))
    # Preserve order while removing duplicate symbols.
    seen, unique = set(), []
    for item in out:
        sym = get_symbol(item)
        if sym and sym not in seen:
            seen.add(sym)
            unique.append(item)
    return unique


def main():
    pre = load(PRE)
    engagement = load(ENGAGEMENT)
    market = load(MARKET)
    ranked = candidates(pre, engagement, market)
    if not ranked:
        raise SystemExit("No selected opportunity to freeze after engagement selection")

    try:
        valid_symbols = trading_symbols()
    except Exception as exc:
        raise SystemExit(str(exc))

    selected = next((x for x in ranked if get_symbol(x) in valid_symbols), None)
    if selected is None:
        bad = [get_symbol(x) for x in ranked[:8]]
        raise SystemExit(f"No valid Binance USDT opportunity found; rejected={bad}")

    symbol_usdt = get_symbol(selected)
    symbol = symbol_usdt[:-4]
    pre["selected_opportunity"] = selected
    pre["recovered_selected_opportunity"] = selected is not pre.get("selected_opportunity")

    frozen = {
        "version": 4,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "symbol_usdt": symbol_usdt,
        "binance_verified": True,
        "category": selected.get("category", ""),
        "reason": selected.get("reason", ""),
        "instruction": selected.get("instruction", ""),
        "score": selected.get("engagement_score", selected.get("adjusted_score", selected.get("raw_score", 0))),
        "run_ai": bool(pre.get("run_ai", False)),
        "selection_source": "validated_engagement_or_market_candidate",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(frozen, indent=2, ensure_ascii=False), encoding="utf-8")
    PRE.write_text(json.dumps(pre, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(frozen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
