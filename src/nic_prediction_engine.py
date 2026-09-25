"""NIC Prediction Engine: evidence-first, walk-forward conditional setup validation.

This module does not claim to predict the market with certainty. It tests whether
the current conditional setup resembles historically testable conditions, combines
that evidence with multi-timeframe market structure, and produces a bounded
prediction-quality score used as a hard pre-publication filter.
"""
from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
FLOW = LIVE / "capital_flow_intelligence.json"
FULL_FLOW = LIVE / "full_universe_flow.json"
MARKET = LIVE / "market_snapshot.json"
REGIME = LIVE / "market_regime_intelligence.json"
POSTMORTEM = LIVE / "nic_prediction_postmortem.json"
OUT = LIVE / "nic_prediction_engine.json"
REPORT = ROOT / "data" / "intelligence" / "nic_prediction_engine_report.json"

BASES = (
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
)
INTERVALS = ("1h", "4h", "1d")
CURRENT_LIMIT = 70
BACKTEST_LIMIT = 220
MIN_EVENTS = 25
MIN_CURRENT_ALIGNMENT = 0.67
MAX_ASSETS = 12


def load(path: Path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default if default is not None else {})) else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


def num(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def get_json(path: str, params: dict) -> object:
    query = urllib.parse.urlencode(params)
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(
                f"{base}{path}?{query}",
                headers={"User-Agent": "binance-square-ai-creator/nic-prediction-engine", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(0.1)
    raise RuntimeError(str(last))


def clean_symbol(value) -> str:
    s = str(value or "").upper().replace("BINANCE:", "").replace("$", "").strip()
    if s.endswith("USDT"):
        s = s[:-4]
    return s if s.isalnum() and 1 <= len(s) <= 15 else ""


def candles(symbol: str, interval: str, limit: int) -> list[dict]:
    raw = get_json("/api/v3/klines", {"symbol": clean_symbol(symbol) + "USDT", "interval": interval, "limit": limit})
    rows = []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, list) or len(row) < 11:
            continue
        try:
            close_time = int(row[6])
            if close_time >= now_ms:
                continue
            rows.append({
                "open_time": int(row[0]),
                "open": num(row[1], 0.0),
                "high": num(row[2], 0.0),
                "low": num(row[3], 0.0),
                "close": num(row[4], 0.0),
                "volume": num(row[5], 0.0),
                "quote_volume": num(row[7], 0.0),
                "taker_buy_quote": num(row[10], 0.0),
                "close_time": close_time,
            })
        except Exception:
            continue
    return rows


def ema(values: list[float], period: int):
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    out = values[0]
    for value in values[1:]:
        out = alpha * value + (1.0 - alpha) * out
    return out


def rsi(values: list[float], period: int = 14):
    if len(values) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def atr(rows: list[dict], period: int = 14):
    if len(rows) < period + 1:
        return None
    trs = []
    for i in range(1, len(rows)):
        cur = rows[i]
        prev = rows[i - 1]
        trs.append(max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev["close"]),
            abs(cur["low"] - prev["close"]),
        ))
    return sum(trs[-period:]) / period


def frame(rows: list[dict]) -> dict:
    closes = [x["close"] for x in rows if x["close"]]
    if len(closes) < 30:
        return {}
    last = closes[-1]
    e20 = ema(closes[-40:], 20)
    e50 = ema(closes[-50:], min(50, len(closes[-50:])))
    a = atr(rows)
    prior_high = max(x["high"] for x in rows[-21:-1])
    prior_low = min(x["low"] for x in rows[-21:-1])
    avg_vol = sum(x["quote_volume"] for x in rows[-21:-1]) / 20
    volume_ratio = rows[-1]["quote_volume"] / avg_vol if avg_vol > 0 else 1.0
    buy_ratio = (
        sum(x["taker_buy_quote"] for x in rows[-20:])
        / max(sum(x["quote_volume"] for x in rows[-20:]), 1e-12)
    )
    return {
        "last": last,
        "ema20": e20,
        "ema50": e50,
        "rsi14": rsi(closes),
        "atr": a,
        "atr_pct": (a / last * 100.0) if a and last else None,
        "volume_ratio": volume_ratio,
        "buy_ratio": buy_ratio,
        "prior_high": prior_high,
        "prior_low": prior_low,
        "close_vs_ema20_pct": ((last / e20) - 1.0) * 100.0 if e20 else 0.0,
        "return_12": ((last / closes[-13]) - 1.0) * 100.0 if len(closes) > 13 and closes[-13] else 0.0,
    }


def current_direction_score(side: str, frames: dict[str, dict], relative_strength: float | None):
    needed = [frames.get("4h") or {}, frames.get("1d") or {}, frames.get("1h") or {}]
    if any(not x for x in needed):
        return 0.0, ["missing_required_timeframe"]

    checks = []
    notes = []
    for name, item in (("1d", frames["1d"]), ("4h", frames["4h"]), ("1h", frames["1h"])):
        trend = bool(item.get("ema20") and item.get("ema50") and (
            item["ema20"] > item["ema50"] if side == "LONG" else item["ema20"] < item["ema50"]
        ))
        momentum = bool(
            (item.get("rsi14") is not None)
            and (50.0 <= item["rsi14"] <= 72.0 if side == "LONG" else 28.0 <= item["rsi14"] <= 50.0)
        )
        checks.extend([trend, momentum])
        notes.append(f"{name}:trend={'ok' if trend else 'no'},momentum={'ok' if momentum else 'no'}")

    alignment = sum(checks) / max(len(checks), 1)
    for item in needed:
        atr_pct = num(item.get("atr_pct"), 0.0)
        if atr_pct > 10.0:
            notes.append("extreme_volatility_penalty")
        elif atr_pct < 0.08:
            notes.append("very_low_volatility")
    if relative_strength is not None:
        rs_ok = relative_strength >= 1.0 if side == "LONG" else relative_strength <= -1.0
        alignment = 0.75 * alignment + 0.25 * (1.0 if rs_ok else 0.0)
        notes.append(f"btc_relative_strength={'ok' if rs_ok else 'no'}")
    return alignment, notes


def event_outcome(rows: list[dict], index: int, side: str):
    if index < 25 or index + 8 >= len(rows):
        return None
    history = rows[:index + 1]
    current = history[-1]
    prior = history[-21:-1]
    if len(prior) < 20:
        return None
    atr_value = atr(history)
    if not atr_value or current["close"] <= 0:
        return None

    closes = [x["close"] for x in history]
    e20 = ema(closes[-40:], 20)
    e50 = ema(closes[-50:], min(50, len(closes[-50:])))
    avg_vol = sum(x["quote_volume"] for x in prior) / 20
    vr = current["quote_volume"] / avg_vol if avg_vol > 0 else 1.0
    r = rsi(closes)
    trend_ok = e20 and e50 and (e20 > e50 if side == "LONG" else e20 < e50)
    momentum_ok = r is not None and (50 <= r <= 72 if side == "LONG" else 28 <= r <= 50)
    if not trend_ok or not momentum_ok or vr < 1.15:
        return None

    prior_high = max(x["high"] for x in prior)
    prior_low = min(x["low"] for x in prior)
    if side == "LONG":
        trigger = prior_high + 0.12 * atr_value
        stop = trigger - 1.0 * atr_value
        target = trigger + 1.8 * atr_value
    else:
        trigger = prior_low - 0.12 * atr_value
        stop = trigger + 1.0 * atr_value
        target = trigger - 1.8 * atr_value

    activated = False
    for future in rows[index + 1:index + 9]:
        high = future["high"]
        low = future["low"]
        if not activated:
            activated = high >= trigger if side == "LONG" else low <= trigger
            if not activated:
                continue
        stop_hit = low <= stop if side == "LONG" else high >= stop
        target_hit = high >= target if side == "LONG" else low <= target
        if stop_hit and target_hit:
            return "AMBIGUOUS"
        if stop_hit:
            return "LOSS"
        if target_hit:
            return "WIN"
    return "NO_TERMINAL_RESULT"


def walk_forward(rows: list[dict], side: str):
    counts = {"WIN": 0, "LOSS": 0, "AMBIGUOUS": 0, "NO_TERMINAL_RESULT": 0}
    events = 0
    for index in range(50, len(rows) - 8):
        outcome = event_outcome(rows, index, side)
        if outcome is None:
            continue
        events += 1
        counts[outcome] += 1
    terminal = counts["WIN"] + counts["LOSS"]
    win_rate = counts["WIN"] / terminal if terminal else None
    return {
        "events": events,
        "wins": counts["WIN"],
        "losses": counts["LOSS"],
        "ambiguous": counts["AMBIGUOUS"],
        "non_terminal": counts["NO_TERMINAL_RESULT"],
        "terminal_samples": terminal,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
    }


def candidate_symbols(flow: dict, full_flow: dict) -> list[tuple[str, str]]:
    out = []
    for row in flow.get("top_conditional_setups") or []:
        if not isinstance(row, dict):
            continue
        setup = row.get("trade_setup") if isinstance(row.get("trade_setup"), dict) else {}
        side = str(setup.get("side") or (row.get("prediction") or {}).get("direction") or "").upper()
        symbol = clean_symbol(row.get("symbol"))
        if symbol and side in {"LONG", "SHORT"}:
            out.append((symbol, side))
    for row in full_flow.get("top_flow_candidates") or []:
        if not isinstance(row, dict):
            continue
        symbol = clean_symbol(row.get("symbol"))
        move = num(row.get("price_change_6h_pct"), num(row.get("price_change_percent"), 0.0))
        if symbol and move:
            out.append((symbol, "LONG" if move > 0 else "SHORT"))
    seen = set()
    final = []
    for x in out:
        if x not in seen:
            seen.add(x)
            final.append(x)
        if len(final) >= MAX_ASSETS:
            break
    return final


def build():
    flow = load(FLOW, {})
    full_flow = load(FULL_FLOW, {})
    market = load(MARKET, {})
    postmortem = load(POSTMORTEM, {})
    candidates = candidate_symbols(flow, full_flow)
    btc_frames = {}
    try:
        for interval in INTERVALS:
            btc_frames[interval] = frame(candles("BTC", interval, CURRENT_LIMIT))
    except Exception:
        btc_frames = {}

    btc_trend = num((btc_frames.get("1d") or {}).get("return_12"), 0.0)
    btc_flow = num((btc_frames.get("1d") or {}).get("buy_ratio"), 0.5)
    fresh_regime = (
        "RISK_ON" if btc_trend > 0 and btc_flow >= 0.51
        else "RISK_OFF" if btc_trend < 0 and btc_flow <= 0.49
        else "MIXED"
    )

    # Fetch current frames and historical 1H evidence concurrently. This stage is
    # deliberately read-only and uses bounded workers to avoid serial network
    # latency dominating the creator cycle.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    fetched = {}
    tasks = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for symbol, side in candidates:
            for interval in INTERVALS:
                tasks.append((symbol, side, interval, "current", executor.submit(candles, symbol, interval, CURRENT_LIMIT)))
            tasks.append((symbol, side, "1h", "historical", executor.submit(candles, symbol, "1h", BACKTEST_LIMIT)))

        for symbol, side, interval, kind, future in tasks:
            try:
                fetched[(symbol, side, interval, kind)] = future.result()
            except Exception:
                fetched[(symbol, side, interval, kind)] = []

    for symbol, side in candidates:
        try:
            frames = {
                interval: frame(fetched.get((symbol, side, interval, "current"), []))
                for interval in INTERVALS
            }
            historical = fetched.get((symbol, side, "1h", "historical"), [])
            relative_strength = None
            btc_1d = (btc_frames.get("1d") or {}).get("return_12")
            asset_1d = (frames.get("1d") or {}).get("return_12")
            if btc_1d is not None and asset_1d is not None:
                relative_strength = asset_1d - btc_1d

            alignment, alignment_notes = current_direction_score(side, frames, relative_strength)
            backtest = walk_forward(historical, side)
            terminal = int(backtest["terminal_samples"])
            smoothed = (backtest["wins"] + 5.0) / (terminal + 10.0) if terminal else 0.5

            quality = 50.0
            quality += (smoothed - 0.5) * 60.0
            quality += (alignment - 0.5) * 28.0

            # Repeated post-fix failure contexts receive a bounded penalty.
            current_regime = fresh_regime
            quality_band = (
                "LT70" if quality < 70 else
                "70_79" if quality < 80 else
                "80_89" if quality < 90 else
                "90_PLUS"
            )
            feedback = postmortem.get("repeated_context_feedback") or []
            for item in feedback:
                if (
                    isinstance(item, dict)
                    and item.get("action") == "PENALIZE_REPEATED_FAILURE"
                    and str(item.get("side") or "").upper() == side
                    and str(item.get("quality_band") or "") == quality_band
                    and str(item.get("regime") or "") == current_regime
                ):
                    penalty = min(8.0, max(0.0, float(item.get("bounded_quality_penalty") or 0.0)))
                    quality -= penalty

            h1 = frames.get("1h") or {}
            if h1.get("volume_ratio", 1.0) >= 1.2:
                quality += 5.0
            if side == "LONG" and relative_strength is not None and relative_strength >= 1.0:
                quality += 5.0
            if side == "SHORT" and relative_strength is not None and relative_strength <= -1.0:
                quality += 5.0

            # Build the live conditional map with the same rule family used by
            # the walk-forward test. A setup is valid only if it remains ahead of
            # the current price; already-triggered moves are treated as late.
            h1_rows = fetched.get((symbol, side, "1h", "current"), [])
            h4 = frames.get("4h") or {}
            h1 = frames.get("1h") or {}
            recommended_setup = {
                "side": side,
                "trigger": None,
                "tp1": None,
                "tp2": None,
                "invalidation": None,
                "risk_per_unit": None,
                "state": "UNAVAILABLE",
            }
            if len(h1_rows) >= 22 and h4.get("atr"):
                prior = h1_rows[-21:-1]
                prior_high = max(x["high"] for x in prior)
                prior_low = min(x["low"] for x in prior)
                atr4 = float(h4["atr"])
                last_price = float(h1.get("last") or 0.0)
                if side == "LONG":
                    trigger = prior_high + 0.12 * atr4
                    if trigger > last_price:
                        stop = trigger - 1.0 * atr4
                        risk = trigger - stop
                        recommended_setup = {
                            "side": side,
                            "trigger": trigger,
                            "tp1": trigger + 1.8 * risk,
                            "tp2": trigger + 2.6 * risk,
                            "invalidation": stop,
                            "risk_per_unit": risk,
                            "state": "AWAITING_TRIGGER",
                            "method": "20-bar breakout + 4H ATR",
                        }
                    else:
                        recommended_setup["state"] = "ALREADY_TRIGGERED_LATE"
                else:
                    trigger = prior_low - 0.12 * atr4
                    if trigger < last_price:
                        stop = trigger + 1.0 * atr4
                        risk = stop - trigger
                        recommended_setup = {
                            "side": side,
                            "trigger": trigger,
                            "tp1": trigger - 1.8 * risk,
                            "tp2": trigger - 2.6 * risk,
                            "invalidation": stop,
                            "risk_per_unit": risk,
                            "state": "AWAITING_TRIGGER",
                            "method": "20-bar breakdown + 4H ATR",
                        }
                    else:
                        recommended_setup["state"] = "ALREADY_TRIGGERED_LATE"

            reasons = list(alignment_notes)
            if terminal < MIN_EVENTS:
                reasons.append(f"insufficient_walk_forward_samples:{terminal}<{MIN_EVENTS}")
                quality = min(quality, 60.0)
            win_rate = num(backtest.get("win_rate"), 0.0)
            if terminal >= MIN_EVENTS and win_rate < 0.55:
                reasons.append(f"historical_win_rate_below_55pct:{win_rate:.3f}")
                quality = min(quality, 66.0)
            if backtest.get("ambiguous", 0) > max(2, terminal * 0.2):
                reasons.append("high_intrabar_ambiguity")
                quality -= 6.0
            atr_pct = num(h1.get("atr_pct"), 0.0)
            if atr_pct > 10:
                reasons.append("extreme_current_volatility")
                quality -= 8.0
            if recommended_setup.get("state") == "ALREADY_TRIGGERED_LATE":
                reasons.append("setup_already_triggered_late")
                quality = min(quality, 55.0)

            quality = round(max(0.0, min(100.0, quality)), 2)
            status = (
                "PASS"
                if terminal >= MIN_EVENTS
                and quality >= 72.0
                and alignment >= MIN_CURRENT_ALIGNMENT
                and recommended_setup.get("state") == "AWAITING_TRIGGER"
                and terminal >= MIN_EVENTS
                and num(backtest.get("win_rate")) >= 0.55
                and not any(x in reasons for x in ("extreme_current_volatility", "high_intrabar_ambiguity"))
                else "WAIT"
            )
            results.append({
                "symbol": symbol,
                "side": side,
                "status": status,
                "quality_score": quality,
                "confidence_ceiling": 85.0,
                "calibrated_confidence": min(85.0, quality),
                "current_alignment": round(alignment, 4),
                "relative_strength_to_btc": round(relative_strength, 4) if relative_strength is not None else None,
                "current_timeframes": {
                    k: {
                        "rsi14": v.get("rsi14"),
                        "atr_pct": v.get("atr_pct"),
                        "volume_ratio": v.get("volume_ratio"),
                        "return_12": v.get("return_12"),
                        "close_vs_ema20_pct": v.get("close_vs_ema20_pct"),
                    } for k, v in frames.items()
                },
                "walk_forward": backtest,
                "recommended_setup": recommended_setup,
                "latest_completed_candle": (
                    {
                        "open_time": h1_rows[-1].get("open_time"),
                        "close_time": h1_rows[-1].get("close_time"),
                        "close": h1_rows[-1].get("close"),
                    }
                    if h1_rows and isinstance(h1_rows[-1], dict) else {}
                ),
                "regime": {
                    "regime": fresh_regime,
                    "btc_1d_return": btc_trend,
                    "btc_1d_buy_ratio": btc_flow,
                    "confidence": None,
                },
                "postmortem_feedback_applied": bool(any(
                    isinstance(x, dict)
                    and x.get("action") == "PENALIZE_REPEATED_FAILURE"
                    and str(x.get("side") or "").upper() == side
                    and str(x.get("regime") or "") == str(regime.get("regime") or "UNKNOWN")
                    for x in feedback
                )),
                "reasons": reasons,
                "policy": {
                    "quality_score_is_not_a_profit_probability": True,
                    "historical_test_is_out_of_sample_only": True,
                    "conditional_trigger_must_be_hit_before_target_or_stop": True,
                    "weak_evidence_means_wait": True,
                },
            })
        except Exception as exc:
            results.append({
                "symbol": symbol,
                "side": side,
                "status": "WAIT",
                "quality_score": 0.0,
                "calibrated_confidence": 0.0,
                "current_alignment": 0.0,
                "relative_strength_to_btc": None,
                "walk_forward": {"events": 0, "wins": 0, "losses": 0, "ambiguous": 0, "non_terminal": 0, "terminal_samples": 0, "win_rate": None},
                "reasons": [f"prediction_engine_error:{type(exc).__name__}"],
            })

    result = {
        "version": "1.0-nic-walk-forward",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY",
        "minimum_walk_forward_events": MIN_EVENTS,
        "minimum_current_alignment": MIN_CURRENT_ALIGNMENT,
        "candidates": results,
        "selected_passes": [x for x in results if x["status"] == "PASS"],
        "selected_waits": [x for x in results if x["status"] != "PASS"],
        "guardrails": [
            "No setup is accepted from a single 1H observation.",
            "Historical outcomes are tested with the trigger-first state machine.",
            "Confidence is shrunk toward neutral when historical sample size is small.",
            "Multi-timeframe disagreement lowers quality.",
            "BTC-relative strength is supporting context, not a causal law.",
            "This engine cannot override safety/publication gates or fabricate a market outcome.",
        ],
    }
    return result


def main() -> int:
    result = build()
    LIVE.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps({
        "version": result["version"],
        "generated_at": result["generated_at"],
        "candidates": len(result["candidates"]),
        "passes": len(result["selected_passes"]),
        "waits": len(result["selected_waits"]),
        "minimum_walk_forward_events": MIN_EVENTS,
        "policy": result["guardrails"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "READY",
        "candidates": len(result["candidates"]),
        "passes": len(result["selected_passes"]),
        "waits": len(result["selected_waits"]),
        "top": sorted(result["candidates"], key=lambda x: x["quality_score"], reverse=True)[:5],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
