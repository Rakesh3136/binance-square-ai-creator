"""Verified prediction ledger and outcome engine."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "analytics/call_ledger.jsonl"
SUMMARY = ROOT / "data/intelligence/call_tracker.json"
TECH = ROOT / "data/live/technical_enrichment.json"
CONTEXT = ROOT / "data/live/publication_context.json"
FROZEN = ROOT / "data/live/authoritative_opportunity.json"
RESULT = ROOT / "data/live/publication_result.json"


def load(path, default):
    try:
        x = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else default
        return x if isinstance(x, type(default)) else default
    except Exception:
        return default


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def now_iso():
    return datetime.now(timezone.utc).isoformat()



def fetch_klines(symbol, start_ms, end_ms):
    """Read public Binance spot candles; no API key is required."""
    rows = []
    cursor = int(start_ms)
    end_ms = int(end_ms)
    for _ in range(20):
        if cursor >= end_ms:
            break
        params = urlencode({
            "symbol": f"{symbol}USDT",
            "interval": "1m",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        })
        try:
            with urlopen(f"https://api.binance.com/api/v3/klines?{params}", timeout=15) as response:
                batch = json.loads(response.read().decode("utf-8"))
        except Exception:
            return rows, "MARKET_DATA_UNAVAILABLE"
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_cursor = last_open + 60000
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if len(batch) < 1000:
            break
    return rows, "OK"


def evaluate_call(call, candles):
    direction = str(call.get("direction") or "").upper()
    targets = [num(x) for x in call.get("targets", []) if num(x) is not None]
    invalidation = num(call.get("invalidation"))
    if not targets or invalidation is None or direction not in {"LONG", "SHORT"}:
        return None
    targets = sorted(targets, reverse=direction == "SHORT")
    hit = set(str(x) for x in (call.get("target_hits") or []))
    for candle in candles:
        high = num(candle[2]); low = num(candle[3])
        if high is None or low is None:
            continue
        if direction == "LONG":
            sl = low <= invalidation
            tp = [i for i, level in enumerate(targets) if high >= level and str(i) not in hit]
        else:
            sl = high >= invalidation
            tp = [i for i, level in enumerate(targets) if low <= level and str(i) not in hit]
        if sl and tp:
            return {"status": "AMBIGUOUS_SAME_CANDLE", "target_hits": sorted(hit), "observed_at": datetime.fromtimestamp(int(candle[0])/1000, timezone.utc).isoformat(), "reason": "Target and invalidation were both inside the same candle; execution order is unknown."}
        for i in tp:
            hit.add(str(i))
        if len(hit) == len(targets):
            return {"status": "TARGETS_COMPLETE", "target_hits": sorted(hit), "observed_at": datetime.fromtimestamp(int(candle[0])/1000, timezone.utc).isoformat()}
        if sl:
            return {"status": "STOP_AFTER_TARGETS" if hit else "STOP_BEFORE_TARGET", "target_hits": sorted(hit), "observed_at": datetime.fromtimestamp(int(candle[0])/1000, timezone.utc).isoformat()}
    return {"status": "OPEN", "target_hits": sorted(hit)}


def refresh_open_outcomes(existing):
    now = datetime.now(timezone.utc)
    changed = False
    for call in existing:
        if call.get("status") != "OPEN" or not call.get("post_id"):
            continue
        try:
            start = datetime.fromisoformat(str(call.get("recorded_at")).replace("Z", "+00:00"))
        except Exception:
            continue
        candles, fetch_status = fetch_klines(str(call.get("symbol") or "").upper(), int(start.timestamp()*1000), int(now.timestamp()*1000))
        if fetch_status != "OK":
            call["outcome_data_status"] = fetch_status
            continue
        outcome = evaluate_call(call, candles)
        if not outcome:
            continue
        call.update({
            "outcome_status": outcome["status"],
            "target_hits": outcome.get("target_hits", []),
            "outcome_checked_at": now.isoformat(),
            "outcome_observation": outcome.get("observed_at"),
        })
        if outcome["status"] != "OPEN":
            call["status"] = "CLOSED"
            call["terminal_outcome"] = outcome["status"]
            call["outcome_verified_by"] = "binance_public_klines"
        changed = True
    return changed


def main():
    context = load(CONTEXT, {})
    frozen = load(FROZEN, {})
    tech = load(TECH, {})
    pub = load(RESULT, {})
    selected = frozen or context
    symbol = str(selected.get("symbol_usdt") or selected.get("symbol") or "").upper().replace("$", "").replace("USDT", "")
    category = str(selected.get("category") or selected.get("content_category") or context.get("category") or "").lower()
    trading_lanes = {
        "technical_setup", "high_volatility", "top_gainers", "top_losers",
        "creator_signal_outcome", "capital_flow", "capital_flow_setup", "conditional_trade",
    }

    status = str(pub.get("status") or "")
    post_id = str(pub.get("post_id") or pub.get("canonical_post_id") or "").strip() or None
    verified_publication = status in {
        "PUBLISHED_VERIFIED_BY_API_RESPONSE",
        "VERIFIED_PUBLISHED",
        "PUBLISHED_AUTONOMOUSLY",
    } and bool(post_id)
    submitted_unknown = status == "PUBLISHED_SUBMITTED_504"
    skipped_publication = status in {
        "PUBLISH_BLOCKED_DUPLICATE",
        "PUBLISH_SKIPPED_WTE_INELIGIBLE",
    }

    # A prediction call is only an experiment when an actual publication exists.
    # This prevents blocked/duplicate drafts from entering the outcome ledger as
    # if readers had received a live call.
    if category not in trading_lanes or not symbol:
        record = {
            "recorded_at": now_iso(),
            "status": "NO_EXPLICIT_CALL",
            "reason": "non-trading editorial lane",
            "category": category,
            "symbol": symbol,
            "publication_status": status,
        }
        if existing:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in existing) + "\n", encoding="utf-8")

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record))
        return 0

    if skipped_publication:
        record = {
            "recorded_at": now_iso(),
            "status": "NO_PUBLICATION",
            "reason": status,
            "category": category,
            "symbol": symbol,
            "post_id": None,
            "publication_status": status,
        }
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False))
        return 0

    if not verified_publication and not submitted_unknown:
        record = {
            "recorded_at": now_iso(),
            "status": "PUBLICATION_UNVERIFIED",
            "reason": "no verified Binance Square post id is available",
            "category": category,
            "symbol": symbol,
            "post_id": post_id,
            "publication_status": status or "NO_PUBLICATION_RESULT",
        }
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False))
        return 0

    # A 504 means submission is unknown, not a verified publication. Do not
    # manufacture a public trading-call experiment from an unverified post.
    if submitted_unknown:
        record = {
            "recorded_at": now_iso(),
            "status": "SUBMITTED_UNKNOWN",
            "reason": "Binance content/add returned HTTP 504 without a canonical post id",
            "category": category,
            "symbol": symbol,
            "post_id": None,
            "publication_status": status,
        }
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False))
        return 0

    price = num(
        tech.get("reference_price")
        or tech.get("current_price")
        or selected.get("reference_price")
        or context.get("reference_price")
    )
    targets = tech.get("targets") if isinstance(tech.get("targets"), list) else []
    invalidation = num(
        tech.get("invalidation")
        or tech.get("stop_loss")
        or tech.get("sl")
        or selected.get("invalidation")
    )
    direction = str(
        tech.get("direction")
        or selected.get("direction")
        or selected.get("side")
        or ""
    ).upper() or "LONG_BIAS"
    explicit = bool(price and (targets or invalidation))

    existing = []
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if isinstance(r, dict):
                    existing.append(r)
            except Exception:
                pass

    linked = None
    now = datetime.now(timezone.utc)
    for r in existing:
        if r.get("status") != "OPEN" or str(r.get("symbol") or "") != symbol:
            continue
        if post_id and str(r.get("post_id") or "") == post_id:
            linked = r
            break
        if r.get("post_id"):
            continue
        try:
            age = now - datetime.fromisoformat(str(r.get("recorded_at")).replace("Z", "+00:00"))
        except Exception:
            age = timedelta(days=99)
        if age <= timedelta(hours=2) and (num(r.get("reference_price")) or 0) == (price or -1):
            linked = r
            break

    record = {
        "recorded_at": now.isoformat(),
        "symbol": symbol,
        "category": category,
        "reference_price": price,
        "targets": [num(x) for x in targets if num(x) is not None],
        "invalidation": invalidation,
        "direction": direction,
        "post_id": post_id,
        "status": "OPEN" if explicit and verified_publication else "NO_EXPLICIT_CALL",
        "verification": "unverified_until_fresh_market_data_confirms_target_or_invalidation",
        "source": "verified technical enrichment + frozen publication context + verified Square publication",
    }

    if linked:
        linked.update({"post_id": post_id or linked.get("post_id"), "category": category})
        lines = []
        for r in existing:
            lines.append(json.dumps(linked if r is linked else r, ensure_ascii=False))
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif explicit and verified_publication:
        record["call_id"] = f"{symbol}-{now.strftime('%Y%m%dT%H%M%SZ')}"
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    refresh_open_outcomes(existing)
    open_calls = [r for r in existing if r.get("status") == "OPEN"]
    if explicit and verified_publication and not linked:
        open_calls.append(record)

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(
        json.dumps(
            {
                "updated_at": now.isoformat(),
                "latest": record,
                "open_calls": open_calls,
                "publication_status": status,
                "publication_verified": verified_publication,
                "rules": [
                    "Never claim a target was hit without fresh verified market data.",
                    "Never rewrite reference price, target or invalidation after publication.",
                    "Failed setups are reported, never hidden.",
                    "Outcome checks use public Binance candles and never rewrite the frozen contract.",
                    "Same-candle target/stop conflicts are marked ambiguous, never guessed.",
                    "Memes never create trading calls.",
                    "Blocked or unverified publications never create an OPEN trading call.",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
