"""NIC Opportunity Desk: evidence-bounded capital rotation watch.

Consumes Creator 23.0's multi-timeframe flow snapshot. It identifies observable
relative-strength/volume/OI divergences; it does not claim to see whale wallets
or know where capital literally moved. It never authorizes publication or trades.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FLOW_PATH = ROOT / "data/live/capital_flow_intelligence.json"
PROJECT_EVIDENCE = ROOT / "data/intelligence/project_fundamentals.jsonl"
MARKET_PATH = ROOT / "data/live/market_snapshot.json"
OUT = ROOT / "data/live/nic_opportunity_desk.json"
VALID_FUNDAMENTALS = {
    "adoption", "developer_activity", "tokenomics", "security",
    "governance", "revenue", "ecosystem_growth", "real_world_usage",
}
LATE_MOVE_PCT = 8.0


def number(value, default=None):
    try:
        n = float(value)
        return n if n == n and abs(n) != float("inf") else default
    except (TypeError, ValueError):
        return default


def read_json(path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default if default is not None else {})) else ({} if default is None else default)
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def read_jsonl(path):
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return rows


def asset_move(asset):
    context = asset.get("market_context") or {}
    if context.get("spot_move_pct") is not None:
        return number(context.get("spot_move_pct"))
    frames = asset.get("timeframes") or {}
    return number((frames.get("1h") or {}).get("return_12"))


def hourly_features(asset):
    frames = asset.get("timeframes") or {}
    h1 = frames.get("1h") or {}
    fut = asset.get("futures") or {}
    return {
        "flow_proxy_score": number((asset.get("multitimeframe") or {}).get("flow_proxy_score"), 50.0),
        "volume_ratio": number(h1.get("volume_ratio")),
        "taker_buy_ratio": number(h1.get("taker_buy_ratio_20")),
        "oi_change_6h_pct": number(fut.get("open_interest_change_6h_pct")),
        "funding_rate": number(fut.get("funding_rate")),
        "confidence": number((asset.get("multitimeframe") or {}).get("confidence")),
    }


def rotation_candidates(document, market=None):
    # Creator 23.0 uses assets; the scheduled production scanner writes v1.3
    # leaders/laggards/top_conditional_setups. Normalize both contracts.
    raw_assets = document.get("assets", [])
    if not raw_assets:
        seen = {}
        for group in ("leaders", "laggards", "top_conditional_setups"):
            for row in document.get(group, []) or []:
                if isinstance(row, dict):
                    key = str(row.get("symbol") or "").upper().replace("USDT", "")
                    if key:
                        seen[key] = row
        raw_assets = list(seen.values())
    market = market if isinstance(market, dict) else {}
    market_rows = {}
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for row in market.get(group, []) or []:
            if isinstance(row, dict):
                key = str(row.get("symbol") or "").upper().replace("USDT", "")
                if key:
                    market_rows[key] = row
    if not any(str(a.get("symbol") or "").upper().replace("USDT", "") == "BTC" for a in raw_assets if isinstance(a, dict)):
        btc_market = market_rows.get("BTC") or {}
        if btc_market:
            raw_assets = list(raw_assets) + [{
                "symbol": "BTC",
                "market_context": {"spot_move_pct": number(btc_market.get("price_change_percent"))},
                "multitimeframe": {"flow_proxy_score": 50.0, "confidence": None},
                "timeframes": {"1h": {}},
                "futures": {},
            }]
    assets = []
    for raw in raw_assets:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        symbol = str(item.get("symbol") or "").upper().replace("USDT", "")
        context = dict(item.get("market_context") or {})
        if context.get("spot_move_pct") is None:
            context["spot_move_pct"] = number((market_rows.get(symbol) or {}).get("price_change_percent"))
        item["market_context"] = context
        if not item.get("multitimeframe"):
            score = number(item.get("flow_score"), 0.0)
            item["multitimeframe"] = {
                "flow_proxy_score": max(0.0, min(100.0, 50.0 + score * 2.0)),
                "confidence": number(item.get("flow_confidence")),
            }
        if not item.get("timeframes"):
            item["timeframes"] = {"1h": {"volume_ratio": item.get("volume_ratio_6h_vs_prior_12h"),
                                            "taker_buy_ratio_20": None}}
        item.setdefault("futures", {})
        assets.append(item)
    btc = next((a for a in assets if str(a.get("symbol", "")).upper() in {"BTC", "BTCUSDT"}), None)
    if not btc:
        return {
            "status": "INSUFFICIENT_BTC_REFERENCE",
            "btc_move_24h_pct": None,
            "candidates": [],
            "reason": "BTC reference is missing; no rotation inference is allowed.",
        }
    btc_move = asset_move(btc)
    if btc_move is None:
        return {
            "status": "INSUFFICIENT_BTC_REFERENCE",
            "btc_move_24h_pct": None,
            "candidates": [],
            "reason": "BTC 24h move is missing; no rotation inference is allowed.",
        }
    falling = btc_move <= -1.0
    candidates = []
    for asset in assets:
        symbol = str(asset.get("symbol") or "").upper().replace("USDT", "")
        if not symbol or symbol == "BTC":
            continue
        move = asset_move(asset)
        if move is None:
            continue
        features = hourly_features(asset)
        rs = number(asset.get("relative_strength_to_btc"))
        if rs is None:
            rs = move - btc_move
        vol = features["volume_ratio"]
        oi = features["oi_change_6h_pct"]
        funding = features["funding_rate"]
        reasons = []
        if falling and rs >= 1.5 and move < LATE_MOVE_PCT and features["flow_proxy_score"] >= 53:
            state = "EARLY_ROTATION_WATCH"
            reasons.extend(["BTC weakness observed", "relative strength versus BTC is positive", "24h move remains below late-move threshold"])
            if vol is not None and vol >= 1.2:
                reasons.append("spot volume acceleration supports participation")
            else:
                reasons.append("volume acceleration is missing or unconfirmed")
            if oi is not None and oi > 0:
                reasons.append("open interest rising; this is positioning evidence, not proof of whale buying")
            else:
                reasons.append("open-interest confirmation missing")
            if funding is not None and funding > 0.001:
                state = "CROWDING_RISK"
                reasons.append("elevated positive funding raises crowded-long risk")
        elif falling and rs <= -1.5 and move <= 0:
            state = "RELATIVE_WEAKNESS_WATCH"
            reasons.append("BTC weakness plus relative underperformance; downside still needs a separate trigger")
        elif move >= LATE_MOVE_PCT:
            state = "LATE_MOVE_DO_NOT_CHASE"
            reasons.append("24h move has crossed the configured late-move threshold")
        else:
            continue
        candidates.append({
            "symbol": symbol, "state": state,
            "asset_move_24h_pct": round(move, 4),
            "btc_move_24h_pct": round(btc_move, 4),
            "relative_strength_vs_btc_pct": round(rs, 4),
            "flow_proxy_score": features["flow_proxy_score"],
            "volume_ratio_1h": vol, "taker_buy_ratio_20": features["taker_buy_ratio"],
            "open_interest_change_6h_pct": oi, "funding_rate": funding,
            "model_confidence": features["confidence"],
            "evidence_reasons": reasons,
            "trade_setup_state": (asset.get("trade_setup") or {}).get("side", "WAIT"),
            "wallet_level_flow_verified": False,
        })
    order = {"EARLY_ROTATION_WATCH": 0, "RELATIVE_WEAKNESS_WATCH": 1, "CROWDING_RISK": 2, "LATE_MOVE_DO_NOT_CHASE": 3}
    candidates.sort(key=lambda x: (order.get(x["state"], 9), -x["relative_strength_vs_btc_pct"]))
    return {
        "status": "ROTATION_CANDIDATES_FOUND" if candidates else "NO_CONFIRMED_ROTATION",
        "btc_move_24h_pct": round(btc_move, 4),
        "btc_weakness_detected": falling,
        "candidates": candidates[:12],
        "interpretation": "These are market-data proxies and divergences, not proof that whales transferred money from BTC into a coin.",
    }


def long_term_watchlist(rows):
    grouped = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").upper().replace("$", "").replace("USDT", "")
        category = str(row.get("evidence_type") or "").lower()
        url = str(row.get("source_url") or row.get("url") or "").strip()
        claim = str(row.get("claim") or row.get("finding") or "").strip()
        if not symbol or category not in VALID_FUNDAMENTALS or not url.startswith("https://") or not claim:
            continue
        try:
            domain = urlparse(url).netloc.lower()
        except ValueError:
            continue
        if not domain:
            continue
        item = grouped.setdefault(symbol, {"symbol": symbol, "evidence": [], "categories": set(), "domains": set()})
        item["evidence"].append({"evidence_type": category, "source_url": url, "source_domain": domain, "claim": claim[:400], "published_at": row.get("published_at")})
        item["categories"].add(category)
        item["domains"].add(domain)
    output = []
    for item in grouped.values():
        cats, domains = item.pop("categories"), item.pop("domains")
        ready = len(cats) >= 3 and len(domains) >= 2
        output.append({
            **item,
            "evidence_categories": sorted(cats),
            "independent_source_domains": len(domains),
            "status": "LONG_TERM_RESEARCH_WATCH" if ready else "INSUFFICIENT_FUNDAMENTAL_EVIDENCE",
            "not_a_price_prediction": True,
            "missing_categories": sorted(VALID_FUNDAMENTALS - cats),
        })
    output.sort(key=lambda x: (x["status"] == "LONG_TERM_RESEARCH_WATCH", len(x["evidence_categories"]), x["independent_source_domains"]), reverse=True)
    return output[:10]


def build(flow_document, fundamentals, market=None):
    rotation = rotation_candidates(flow_document, market)
    long_term = long_term_watchlist(fundamentals)
    return {
        "schema_version": "NIC-OPPORTUNITY-DESK-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY",
        "capital_rotation": rotation,
        "long_term_project_watchlist": long_term,
        "truth_boundaries": [
            "Public spot/futures indicators are proxies, not literal wallet-level money flows.",
            "A coin outperforming BTC during a BTC decline is a watchlist signal, not a guaranteed pump.",
            "Long-term project thesis requires independent evidence across multiple fundamental categories and source domains.",
            "No entry, publication, or investment action is authorized by this report.",
        ],
    }


def main():
    flow_document = read_json(FLOW_PATH, {})
    fundamentals = read_jsonl(PROJECT_EVIDENCE)
    market = read_json(MARKET_PATH, {})
    report = build(flow_document, fundamentals, market)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "rotation_status": report["capital_rotation"]["status"],
        "rotation_candidates": len(report["capital_rotation"]["candidates"]),
        "long_term_projects": len(report["long_term_project_watchlist"]),
        "output": str(OUT.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
