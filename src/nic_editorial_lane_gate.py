"""Fail-closed eligibility for the editorial-only publication lane."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
OUT = LIVE / "nic_editorial_lane_gate.json"
MAX_SETUP_MOVE_24H_PCT = 5.0
SETUP_TERMS = re.compile(r"\b(support|resistance|entry|stop[- ]?loss|invalidation|target|take[- ]?profit|long bias|short bias|breakout|setup)\b", re.I)
ACTIONABLE_TERMS = re.compile(r"\b(entry\s*[:=@]|stop[- ]?loss\s*[:=@]|take[- ]?profit\s*[:=@]|\bSL\s*/\s*TP\b|buy now|sell now|open (?:a )?(?:long|short)|enter (?:a )?(?:long|short)|leverage\s*[:=])", re.I)

def fresh(data, max_age_minutes=45):
    raw = str(data.get("generated_at") or data.get("timestamp") or "").strip()
    if not raw:
        return False
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 60
        return 0 <= age <= max_age_minutes
    except Exception:
        return False

def _symbol(value):
    s = str(value or "").upper().replace("BINANCE:", "").replace("$", "").strip()
    return s[:-4] if s.endswith("USDT") else s

def _draft_text(report):
    draft = report.get("draft") if isinstance(report.get("draft"), dict) else report
    for key in ("post", "text", "body", "content"):
        if draft.get(key):
            return str(draft[key])
    return ""

def _setup_market_check(text, symbol, market):
    """Only setup-like posts need extension screening; missing evidence blocks them."""
    if not SETUP_TERMS.search(text):
        return []
    reasons = []
    if ACTIONABLE_TERMS.search(text):
        reasons.append("editorial lane contains actionable trade instructions/levels")
    if not symbol:
        return reasons + ["setup-like editorial has no selected symbol"]
    if not fresh(market, max_age_minutes=15):
        return reasons + ["setup-like editorial lacks fresh market snapshot"]
    found = None
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market", "early_movers"):
        rows = market.get(group) if isinstance(market.get(group), list) else []
        for row in rows:
            if not isinstance(row, dict) or _symbol(row.get("symbol") or row.get("symbol_usdt")) != symbol:
                continue
            try:
                found = float(row.get("price_change_percent"))
            except (TypeError, ValueError):
                found = None
            break
        if found is not None:
            break
    if found is None:
        reasons.append("setup-like editorial has no matching asset 24h move evidence")
    elif abs(found) > MAX_SETUP_MOVE_24H_PCT:
        reasons.append("asset already extended; setup-like editorial blocked from fresh promotion")
    return reasons

def evaluate(eligibility, routing, challenge, draft=None, market=None, symbol=""):
    reasons = []
    if eligibility.get("eligible") is not True:
        reasons.append("current-cycle publication eligibility is not true")
    if str(eligibility.get("publication_mode") or "").upper() != "EDITORIAL":
        reasons.append("publication mode is not EDITORIAL")
    if eligibility.get("trade_authorized") is not False:
        reasons.append("editorial lane must explicitly deny trade authorization")
    if routing.get("publish") is not True:
        reasons.append("Signal-First did not authorize this cycle for publication")
    decision = str(challenge.get("decision") or "").upper()
    if decision not in {"EDITORIAL_SIGNAL", "EDITORIAL", "RESEARCH", "NO_TRADE"}:
        reasons.append("current decision is not an editorial/research decision")
    if not fresh(eligibility):
        reasons.append("publication eligibility is missing or stale")
    if not fresh(routing):
        reasons.append("Signal-First routing decision is missing or stale")
    if not fresh(challenge):
        reasons.append("counterfactual challenge decision is missing or stale")
    if draft is not None:
        text = _draft_text(draft)
        if not text.strip():
            reasons.append("current editorial draft is empty or unreadable")
        else:
            reasons.extend(_setup_market_check(text, _symbol(symbol), market or {}))
    ok = not reasons
    return {
        "schema": "NIC-EDITORIAL-LANE-1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "EDITORIAL_ELIGIBLE" if ok else "BLOCKED",
        "publish": ok,
        "publication_mode": "EDITORIAL" if ok else "BLOCKED",
        "trade_authorized": False,
        "reasons": reasons,
        "setup_move_limit_24h_pct": MAX_SETUP_MOVE_24H_PCT,
        "policy": "Editorial permission only. Actionable trade instructions/levels are blocked. Setup-like posts require fresh matching market evidence and are blocked after an extended move."
    }

def main():
    def load_path(path):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    def load(name):
        return load_path(LIVE / name)
    draft_path = Path(os.environ["DRAFT_PATH"]) if os.environ.get("DRAFT_PATH") else None
    draft_report = load_path(draft_path) if draft_path and draft_path.exists() else None
    pre = load("editorial_preflight.json")
    selected = pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"), dict) else {}
    context = load("publication_context.json")
    symbol = selected.get("symbol") or context.get("symbol") or ((draft_report or {}).get("draft") or {}).get("symbol")
    result = evaluate(
        load("nic22_5_publication_eligibility.json"),
        load("signal_first_routing.json"),
        load("nic23_5_counterfactual_challenge.json"),
        draft=draft_report,
        market=load("market_snapshot.json"),
        symbol=symbol or "",
    )
    LIVE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["publish"] else 24

if __name__ == "__main__":
    raise SystemExit(main())
