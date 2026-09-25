"""Historical prediction audit for previously published conditional calls.

Parses immutable levels from verified Square publication logs and evaluates the
first post-publication 1H event using a trigger-first state machine. This is a
diagnostic dataset only: legacy calls are never used as clean calibration data
for the post-fix predictor.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "analytics" / "publication_log.jsonl"
OUT = ROOT / "data" / "live" / "nic_historical_prediction_audit.jsonl"
REPORT = ROOT / "data" / "intelligence" / "nic_historical_prediction_audit_report.json"

BASES = (
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
)
TRADING_CATEGORIES = {
    "technical_setup", "high_volatility", "top_gainers", "top_losers",
    "creator_signal_outcome", "capital_flow", "capital_flow_setup",
    "capital_flow_long", "capital_flow_short", "conditional_trade",
    "follow_up", "flow",
}
LEVEL_RE = re.compile(
    r"Entry trigger:\s*([0-9.]+).*?"
    r"TP1:\s*([0-9.]+).*?"
    r"TP2:\s*([0-9.]+).*?"
    r"SL\s*/\s*invalidation:\s*([0-9.]+)",
    re.I | re.S,
)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict):
                out.append(x)
        except Exception:
            pass
    return out


def dt(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def fetch_klines(symbol, start_ms, end_ms):
    q = urllib.parse.urlencode({
        "symbol": f"{symbol}USDT",
        "interval": "1h",
        "startTime": int(start_ms),
        "endTime": int(end_ms),
        "limit": 1000,
    })
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(
                f"{base}/api/v3/klines?{q}",
                headers={"User-Agent": "binance-square-ai-creator/nic-historical-audit", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode("utf-8"))
            return [r for r in raw if isinstance(r, list) and len(r) >= 7]
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))


def evaluate(direction, trigger, tp1, invalidation, candles):
    direction = direction.upper().replace("_BIAS", "")
    activated = False
    trigger_time = None
    for row in candles:
        try:
            high = float(row[2])
            low = float(row[3])
            stamp = datetime.fromtimestamp(int(row[0]) / 1000, timezone.utc)
        except Exception:
            continue

        if not activated:
            hit = high >= trigger if direction == "LONG" else low <= trigger
            if not hit:
                continue
            activated = True
            trigger_time = stamp

        stop = low <= invalidation if direction == "LONG" else high >= invalidation
        target = high >= tp1 if direction == "LONG" else low <= tp1
        if stop and target:
            return "AMBIGUOUS", activated, trigger_time, stamp
        if target:
            return "TP1_HIT", activated, trigger_time, stamp
        if stop:
            return "STOP_AFTER_TRIGGER", activated, trigger_time, stamp

    if not activated:
        return "UNTRIGGERED", False, None, None
    return "OPEN", True, trigger_time, None


def main() -> int:
    rows = read_jsonl(LOG)
    records = []
    seen = set()
    now = datetime.now(timezone.utc)

    for row in rows:
        if str(row.get("status") or "") not in {
            "PUBLISHED_VERIFIED_BY_API_RESPONSE",
            "VERIFIED_PUBLISHED",
            "PUBLISHED_AUTONOMOUSLY",
        }:
            continue
        category = str(row.get("category") or "").lower()
        if category not in TRADING_CATEGORIES:
            continue

        post_id = str(row.get("canonical_post_id") or row.get("post_id") or "")
        symbol = re.sub(r"USDT$", "", str(row.get("symbol") or "").upper())
        published = dt(row.get("published_at") or row.get("timestamp"))
        if not post_id or not symbol or not published or post_id in seen:
            continue

        text = str(row.get("text") or row.get("post") or "")
        m = LEVEL_RE.search(text)
        if not m:
            continue

        trigger, tp1, tp2, invalidation = [float(x) for x in m.groups()]
        direction = str(row.get("direction") or "").upper()
        if direction not in {"LONG", "SHORT"}:
            direction = "LONG" if " LONG" in text.upper() or " LONG
" in text.upper() else "SHORT"

        end = min(now, published + timedelta(hours=120))
        try:
            candles = fetch_klines(symbol, int(published.timestamp() * 1000), int(end.timestamp() * 1000))
        except Exception as exc:
            records.append({
                "post_id": post_id,
                "symbol": symbol,
                "direction": direction,
                "published_at": published.isoformat(),
                "status": "DATA_UNAVAILABLE",
                "error": type(exc).__name__,
            })
            seen.add(post_id)
            continue

        outcome, activated, trigger_time, terminal_time = evaluate(
            direction, trigger, tp1, invalidation, candles
        )
        records.append({
            "post_id": post_id,
            "symbol": symbol,
            "category": category,
            "direction": direction,
            "published_at": published.isoformat(),
            "trigger": trigger,
            "tp1": tp1,
            "tp2": tp2,
            "invalidation": invalidation,
            "outcome": outcome,
            "trigger_activated": activated,
            "trigger_activated_at": trigger_time.isoformat() if trigger_time else None,
            "terminal_at": terminal_time.isoformat() if terminal_time else None,
            "evaluator_version": "1.0-historical-trigger-first",
            "calibration_eligible": False,
            "policy": "Diagnostic legacy call audit only; not clean post-fix calibration data.",
        })
        seen.add(post_id)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records),
        encoding="utf-8",
    )

    counted = [x for x in records if x.get("outcome") in {
        "TP1_HIT", "STOP_AFTER_TRIGGER", "AMBIGUOUS", "UNTRIGGERED", "OPEN"
    }]
    summary = {}
    for key in ("LONG", "SHORT"):
        subset = [x for x in counted if x.get("direction") == key]
        summary[key] = {
            "samples": len(subset),
            "tp1_hit": sum(x.get("outcome") == "TP1_HIT" for x in subset),
            "stop_after_trigger": sum(x.get("outcome") == "STOP_AFTER_TRIGGER" for x in subset),
            "ambiguous": sum(x.get("outcome") == "AMBIGUOUS" for x in subset),
            "untriggered": sum(x.get("outcome") == "UNTRIGGERED" for x in subset),
            "open": sum(x.get("outcome") == "OPEN" for x in subset),
        }

    total = {
        "samples": len(counted),
        "tp1_hit": sum(x.get("outcome") == "TP1_HIT" for x in counted),
        "stop_after_trigger": sum(x.get("outcome") == "STOP_AFTER_TRIGGER" for x in counted),
        "ambiguous": sum(x.get("outcome") == "AMBIGUOUS" for x in counted),
        "untriggered": sum(x.get("outcome") == "UNTRIGGERED" for x in counted),
        "open": sum(x.get("outcome") == "OPEN" for x in counted),
    }

    report = {
        "version": "1.0-historical-trigger-first",
        "generated_at": now.isoformat(),
        "records_audited": len(counted),
        "by_direction": summary,
        "total": total,
        "calibration_note": "Historical calls are diagnostic only because their original generation process differs from post-fix NIC.",
        "structural_lessons": [
            "UNTRIGGERED is not a prediction loss; it means the conditional thesis never activated.",
            "A stop is only evaluated after trigger activation.",
            "Same-candle stop/target conflicts are ambiguous.",
            "Legacy engagement outcomes are not substitutes for market outcomes.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
