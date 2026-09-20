"""Freeze the exact market state used by a Signal-First prediction.

The snapshot is immutable input for chart rendering and later outcome evaluation.
Only information available at signal creation is allowed into the chart dataset.
Incomplete candles are excluded; the exact signal price is stored separately.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "data/live/signal_first_routing.json"
AUTH = ROOT / "data/live/authoritative_opportunity.json"
OUT = ROOT / "data/live/historical_setup_snapshot.json"
HOUR_MS = 60 * 60 * 1000


def load(path: Path, default=None):
    if default is None:
        default = {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def parse_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def normal_symbol(value) -> str:
    return str(value or "").upper().replace("BINANCE:", "").replace("$", "").replace("USDT", "").strip()


def candle_row(row):
    if isinstance(row, dict):
        return {
            "open_time": int(row["open_time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0)),
        }
    if isinstance(row, (list, tuple)) and len(row) >= 6:
        return {
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
    raise ValueError("invalid OHLCV row")


def main():
    routing = load(ROUTING, {})
    auth = load(AUTH, {})
    selected = routing.get("selected") if isinstance(routing.get("selected"), dict) else {}
    if not selected:
        selected = auth
    if routing.get("decision") != "PRIMARY_SIGNAL" or routing.get("prediction_contract_complete") is False:
        raise SystemExit("Historical snapshot requires an authoritative Signal-First prediction")

    created_at = str(routing.get("generated_at") or auth.get("frozen_at") or "").strip()
    if not created_at:
        raise SystemExit("Signal creation timestamp missing")
    signal_ms = parse_ms(created_at)

    symbol = normal_symbol(selected.get("symbol") or auth.get("symbol"))
    if not symbol:
        raise SystemExit("Signal symbol missing")

    # The selected market snapshot contains the evidence available to the router.
    # Store only completed 1H candles: an open candle can contain information from
    # after the exact prediction timestamp and would create look-ahead bias.
    raw = selected.get("candles_1h") or []
    candles = []
    for row in raw:
        try:
            c = candle_row(row)
        except Exception:
            continue
        if c["open_time"] + HOUR_MS <= signal_ms:
            candles.append(c)
    candles.sort(key=lambda x: x["open_time"])
    if len(candles) < 3:
        raise SystemExit(f"Historical snapshot has too few completed 1H candles: {len(candles)}")

    prediction = selected.get("prediction") if isinstance(selected.get("prediction"), dict) else {}
    setup = selected.get("trade_setup") if isinstance(selected.get("trade_setup"), dict) else {}
    direction = str(setup.get("side") or prediction.get("direction") or selected.get("direction") or "").upper()
    entry = setup.get("trigger", prediction.get("entry_trigger", selected.get("entry_trigger")))
    tp1 = setup.get("tp1", prediction.get("tp1", selected.get("tp1")))
    tp2 = setup.get("tp2", prediction.get("tp2", selected.get("tp2")))
    sl = setup.get("invalidation", prediction.get("sl", selected.get("sl")))
    signal_price = selected.get("last_price", selected.get("price"))

    # Keep the exact price separately from candle closes. This is the value the
    # signal saw at creation time; it is not retroactively reconstructed.
    if signal_price is None:
        signal_price = candles[-1]["close"]

    snapshot = {
        "schema_version": 1,
        "status": "FROZEN",
        "snapshot_type": "HISTORICAL_SIGNAL_SETUP",
        "signal_created_at": datetime.fromtimestamp(signal_ms / 1000, tz=timezone.utc).isoformat(),
        "signal_created_at_ms": signal_ms,
        "symbol": symbol,
        "symbol_usdt": symbol + "USDT",
        "timeframe": "1H",
        "data_cutoff": iso_ms(signal_ms),
        "candle_policy": "completed_candles_only",
        "lookahead_protection": True,
        "source": "Signal-First router market snapshot",
        "signal_price": float(signal_price),
        "prediction": {
            "direction": direction,
            "entry_trigger": entry,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "confidence": prediction.get("confidence", selected.get("confidence")),
            "conditional": True,
            "not_a_guarantee": True,
        },
        "candles_1h": candles[-48:],
        "candle_count": min(len(candles), 48),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        old = load(OUT, {})
        if old.get("status") == "FROZEN" and old.get("signal_created_at") == snapshot["signal_created_at"] and old.get("symbol") == symbol:
            print(json.dumps({"status": "ALREADY_FROZEN", "path": str(OUT), "signal_created_at": old.get("signal_created_at")}, indent=2))
            return
        raise SystemExit("Refusing to overwrite an existing historical setup snapshot")

    OUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "HISTORICAL_SNAPSHOT_FROZEN",
        "symbol": symbol,
        "signal_created_at": snapshot["signal_created_at"],
        "data_cutoff": snapshot["data_cutoff"],
        "candles": snapshot["candle_count"],
        "lookahead_protection": True,
    }, indent=2))


if __name__ == "__main__":
    main()
