"""Creator 23.0 — multi-timeframe capital-flow and rotation intelligence.

This module studies BTC/ETH/BNB plus a liquid set of Binance USDT assets across
1h, 4h, 12h and 1d data. It estimates *flow proxies* from spot taker-buy mix,
volume acceleration, futures open-interest/funding signals, relative strength,
trend alignment and volatility. It never treats these proxies as literal money
flows or guaranteed forecasts.

The output is a research/education layer for content generation. It can produce
conditional LONG/SHORT/WAIT setups with evidence-derived trigger, invalidation,
and model risk/target levels. It never places trades, never manages positions,
and never claims certainty.
"""
from __future__ import annotations

import json, math, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/live/market_snapshot.json"
NEWS = ROOT / "data/live/news_snapshot.json"
PREFLIGHT = ROOT / "data/live/editorial_preflight.json"
OUT = ROOT / "data/live/capital_flow_intelligence.json"
REPORT = ROOT / "data/intelligence/capital_flow_report.json"

SPOT_BASE = "https://api.binance.com"
FAPI_BASE = "https://fapi.binance.com"
INTERVALS = ("1h", "4h", "12h", "1d")
MAJORS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")
MAX_ASSETS = 12
KLINE_LIMIT = 90
TIMEOUT = 15


def load(path: Path, default=None):
    if default is None:
        default = {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def num(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def clamp(x, lo=0.0, hi=100.0):
    return round(max(lo, min(hi, x)), 3)


def sym(value):
    return re.sub(r"USDT$", "", str(value or "").upper().replace("$", "").strip())


def get_json(base: str, path: str, params: dict):
    query = urlencode(params)
    req = Request(f"{base}{path}?{query}", headers={"User-Agent": "binance-square-ai-creator/23.0", "Accept": "application/json"})
    last = None
    for attempt in range(2):
        try:
            with urlopen(req, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.35)
    raise RuntimeError(str(last))


def spot_klines(symbol: str, interval: str):
    data = get_json(SPOT_BASE, "/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": KLINE_LIMIT})
    rows = []
    for r in data if isinstance(data, list) else []:
        if not isinstance(r, list) or len(r) < 11:
            continue
        rows.append({
            "open_time": int(r[0]), "open": num(r[1]), "high": num(r[2]), "low": num(r[3]),
            "close": num(r[4]), "volume": num(r[5]), "quote_volume": num(r[7]),
            "trades": int(num(r[8])), "taker_buy_base": num(r[9]), "taker_buy_quote": num(r[10]),
        })
    return rows


def futures_metrics(symbol: str):
    out = {"available": False, "funding_rate": None, "open_interest_change_pct": None, "taker_buy_sell_ratio": None, "long_short_ratio": None}
    if symbol not in MAJORS and not symbol.endswith("USDT"):
        return out
    try:
        funding = get_json(FAPI_BASE, "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 8})
        if funding:
            out["funding_rate"] = num(funding[-1].get("fundingRate"))
            out["funding_rate_8"] = [num(x.get("fundingRate")) for x in funding if isinstance(x, dict)]
            out["available"] = True
    except Exception:
        pass
    try:
        oi = get_json(FAPI_BASE, "/futures/data/openInterestHist", {"symbol": symbol, "period": "1h", "limit": 12})
        if oi:
            vals = [num(x.get("sumOpenInterestValue")) for x in oi if isinstance(x, dict)]
            if len(vals) >= 2 and vals[-2] > 0:
                out["open_interest_change_pct"] = (vals[-1] / vals[-2] - 1.0) * 100.0
            if len(vals) >= 6 and vals[-6] > 0:
                out["open_interest_change_6h_pct"] = (vals[-1] / vals[-6] - 1.0) * 100.0
            out["available"] = True
    except Exception:
        pass
    try:
        ts = get_json(FAPI_BASE, "/futures/data/takerlongshortRatio", {"symbol": symbol, "period": "1h", "limit": 12})
        if ts:
            latest = ts[-1]
            ratio = num(latest.get("buySellRatio"))
            if ratio > 0:
                out["taker_buy_sell_ratio"] = ratio
                out["available"] = True
    except Exception:
        pass
    try:
        ls = get_json(FAPI_BASE, "/futures/data/globalLongShortAccountRatio", {"symbol": symbol, "period": "1h", "limit": 12})
        if ls:
            ratio = num(ls[-1].get("longShortRatio"))
            if ratio > 0:
                out["long_short_ratio"] = ratio
                out["available"] = True
    except Exception:
        pass
    return out


def ema(values, period):
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1.0 - alpha) * result
    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(0.0, d)); losses.append(max(0.0, -d))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        cur, prev = candles[i], candles[i-1]
        trs.append(max(cur["high"] - cur["low"], abs(cur["high"] - prev["close"]), abs(cur["low"] - prev["close"])))
    return sum(trs[-period:]) / period


def ret(values, bars):
    if len(values) <= bars or values[-bars-1] == 0:
        return 0.0
    return (values[-1] / values[-bars-1] - 1.0) * 100.0


def volume_ratio(candles, period=20):
    if len(candles) < period + 1:
        return 1.0
    base = sum(x["quote_volume"] for x in candles[-period-1:-1]) / period
    return candles[-1]["quote_volume"] / base if base > 0 else 1.0


def buy_ratio(candles):
    if not candles:
        return 0.5
    q = sum(x["taker_buy_quote"] for x in candles[-20:])
    v = sum(x["quote_volume"] for x in candles[-20:])
    return q / v if v > 0 else 0.5


def structure(candles):
    if len(candles) < 25:
        return {"breakout": 0, "support": None, "resistance": None}
    closes = [x["close"] for x in candles]
    highs = [x["high"] for x in candles[-21:-1]]
    lows = [x["low"] for x in candles[-21:-1]]
    last = closes[-1]
    hi, lo = max(highs), min(lows)
    return {"breakout": 1 if last > hi else (-1 if last < lo else 0), "support": lo, "resistance": hi}


def frame_features(candles):
    closes = [x["close"] for x in candles]
    if not closes:
        return {}
    last = closes[-1]
    e20, e50 = ema(closes[-50:], 20), ema(closes[-50:], min(50, len(closes)))
    a = atr(candles)
    st = structure(candles)
    vr = volume_ratio(candles)
    br = buy_ratio(candles)
    trend = clamp(50 + (20 if e20 and e50 and e20 > e50 else -20) + (10 if last > e20 else -10))
    momentum = clamp(50 + ret(closes, 3) * 2.5 + ret(closes, min(12, len(closes)-1)) * 1.2)
    flow = clamp(50 + (br - 0.5) * 120 + (vr - 1.0) * 12)
    return {"last": last, "ema20": e20, "ema50": e50, "rsi14": rsi(closes), "atr": a, "atr_pct": (a / last * 100) if a and last else None, "return_3": ret(closes, 3), "return_12": ret(closes, min(12, len(closes)-1)), "volume_ratio": vr, "taker_buy_ratio_20": br, "trend_score": trend, "momentum_score": momentum, "flow_score": flow, "structure": st}


def candidates_from_market(market):
    items = {}
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for x in market.get(group) or []:
            if not isinstance(x, dict):
                continue
            s = str(x.get("symbol") or "").upper()
            if not s.endswith("USDT"):
                continue
            items[s] = x
    ranked = sorted(items.values(), key=lambda x: num(x.get("quote_volume_usdt") or x.get("quote_volume")), reverse=True)
    names = [m for m in MAJORS if m in items] + [str(x.get("symbol")).upper() for x in ranked if str(x.get("symbol")).upper() not in MAJORS]
    out = []
    for s in names:
        if s not in out:
            out.append(s)
        if len(out) >= MAX_ASSETS:
            break
    return out


def market_context(market, symbol):
    for group in ("top_content_signals", "top_gainers", "top_losers", "highest_volume", "new_listing_market"):
        for x in market.get(group) or []:
            if isinstance(x, dict) and str(x.get("symbol") or "").upper() == symbol:
                return x
    return {}


def build_asset(market, symbol):
    frames = {}
    errors = []
    for interval in INTERVALS:
        try:
            frames[interval] = frame_features(spot_klines(symbol, interval))
        except Exception as exc:
            errors.append(f"{interval}:{type(exc).__name__}")
    fut = futures_metrics(symbol)
    d = frames.get("1d") or {}; h12 = frames.get("12h") or {}; h4 = frames.get("4h") or {}; h1 = frames.get("1h") or {}
    closes = [x.get("last") for x in (h1,h4,h12,d) if x.get("last")]
    last = closes[0] if closes else num(market_context(market, symbol).get("last_price"))
    mtf_trend = sum((f.get("trend_score",50) - 50) * w for f,w in ((d,0.32),(h12,0.28),(h4,0.25),(h1,0.15))) + 50
    mtf_momentum = sum((f.get("momentum_score",50) - 50) * w for f,w in ((d,0.28),(h12,0.28),(h4,0.26),(h1,0.18))) + 50
    mtf_flow = sum((f.get("flow_score",50) - 50) * w for f,w in ((d,0.25),(h12,0.28),(h4,0.30),(h1,0.17))) + 50
    aligned_bull = all((f.get("trend_score",50) >= 55 and f.get("momentum_score",50) >= 50) for f in (d,h12,h4) if f)
    aligned_bear = all((f.get("trend_score",50) <= 45 and f.get("momentum_score",50) <= 50) for f in (d,h12,h4) if f)
    oi = fut.get("open_interest_change_6h_pct")
    funding = fut.get("funding_rate")
    flow_adjust = 0.0
    flow_notes = []
    if oi is not None:
        if mtf_momentum >= 55 and oi > 1.0: flow_adjust += 8; flow_notes.append("price_up_plus_OI_up")
        elif mtf_momentum <= 45 and oi > 1.0: flow_adjust -= 8; flow_notes.append("price_down_plus_OI_up")
        elif abs(oi) < 0.5: flow_notes.append("OI_flat")
        elif oi < -1.0: flow_notes.append("OI_unwinding")
    if funding is not None:
        if funding > 0.0008: flow_adjust -= 6; flow_notes.append("positive_funding_crowding")
        elif funding < -0.0005: flow_adjust += 4; flow_notes.append("negative_funding_pressure")
    taker = fut.get("taker_buy_sell_ratio")
    if taker is not None:
        if taker > 1.08: flow_adjust += 5; flow_notes.append("futures_taker_buy_dominance")
        elif taker < 0.92: flow_adjust -= 5; flow_notes.append("futures_taker_sell_dominance")
    flow_score = clamp(mtf_flow + flow_adjust)
    context = market_context(market, symbol)
    quote_volume = num(context.get("quote_volume_usdt") or context.get("quote_volume"))
    liquidity_score = clamp(25 + math.log10(max(quote_volume,1)) * 9)
    relative_to_btc = None
    return_1d = d.get("return_12")
    # Use BTC's daily-frame return supplied later by the caller where possible.
    structure_4 = h4.get("structure") or {}
    atr4 = h4.get("atr") or 0.0
    trigger = None; invalidation = None; tp1 = None; tp2 = None; side = "WAIT"
    confidence = clamp(0.35*mtf_trend + 0.25*mtf_momentum + 0.25*flow_score + 0.15*liquidity_score)
    if aligned_bull and flow_score >= 58 and confidence >= 62 and last and atr4:
        side = "LONG"
        resistance = num(structure_4.get("resistance"), last)
        trigger = max(last, resistance + 0.12*atr4)
        invalidation = trigger - 1.0*atr4
        risk = max(trigger - invalidation, 1e-12)
        tp1, tp2 = trigger + 1.8*risk, trigger + 2.6*risk
    elif aligned_bear and flow_score <= 44 and confidence >= 62 and last and atr4:
        side = "SHORT"
        support = num(structure_4.get("support"), last)
        trigger = min(last, support - 0.12*atr4)
        invalidation = trigger + 1.0*atr4
        risk = max(invalidation - trigger, 1e-12)
        tp1, tp2 = trigger - 1.8*risk, trigger - 2.6*risk
    if liquidity_score < 55:
        side = "WAIT"
    if errors:
        confidence = clamp(confidence - 8)
    return {"symbol": sym(symbol), "last_price": last, "timeframes": frames, "futures": fut, "multitimeframe": {"trend_score": clamp(mtf_trend), "momentum_score": clamp(mtf_momentum), "flow_proxy_score": flow_score, "bull_alignment": aligned_bull, "bear_alignment": aligned_bear, "confidence": confidence}, "market_context": {"quote_volume_usdt": quote_volume, "liquidity_score": liquidity_score, "spot_move_pct": num(context.get("price_change_percent"))}, "flow_notes": flow_notes, "relative_strength_to_btc": relative_to_btc, "trade_setup": {"side": side, "trigger": trigger, "invalidation": invalidation, "tp1": tp1, "tp2": tp2, "risk_reward_tp1": 1.8 if trigger is not None else None, "basis": "multi-timeframe trend + flow proxies + ATR structure" if trigger is not None else "insufficient alignment"}, "data_quality": {"missing_intervals": errors, "futures_metrics_available": fut.get("available",False)}, "epistemic_status": "DERIVED_OBSERVATION_WITH_CONDITIONAL_SETUP"}


def apply_relative_strength(assets):
    btc = next((x for x in assets if x.get("symbol") == "BTC"), None)
    btc_ret = None
    if btc:
        btc_ret = ((btc.get("timeframes") or {}).get("1d") or {}).get("return_12")
    for a in assets:
        ret1 = ((a.get("timeframes") or {}).get("1d") or {}).get("return_12")
        if btc_ret is None or ret1 is None:
            a["relative_strength_to_btc"] = None
            continue
        rs = ret1 - btc_ret
        a["relative_strength_to_btc"] = round(rs,3)
        a["rotation_signal"] = "OUTPERFORMING_BTC" if rs >= 2.0 else ("UNDERPERFORMING_BTC" if rs <= -2.0 else "TRACKING_BTC")
        setup = a.get("trade_setup") or {}
        if setup.get("side") == "LONG" and rs < 0:
            setup["side"] = "WAIT"; setup["basis"] = "long alignment but relative strength does not confirm BTC leadership"
        if setup.get("side") == "SHORT" and rs > 0:
            setup["side"] = "WAIT"; setup["basis"] = "short alignment but asset is outperforming BTC"


def rotation_map(assets):
    btc = next((x for x in assets if x.get("symbol") == "BTC"), None)
    btc_flow = num((((btc or {}).get("multitimeframe") or {}).get("flow_proxy_score")), 50)
    btc_trend = num((((btc or {}).get("multitimeframe") or {}).get("trend_score")), 50)
    regime = "RISK_ON" if btc_trend >= 58 and btc_flow >= 55 else ("RISK_OFF" if btc_trend <= 42 and btc_flow <= 45 else "MIXED")
    ranked=[]
    for a in assets:
        if a.get("symbol") == "BTC":
            continue
        m=a.get("multitimeframe") or {}; rs=num(a.get("relative_strength_to_btc"),0)
        score = clamp(50 + (m.get("flow_proxy_score",50)-50)*0.45 + (m.get("momentum_score",50)-50)*0.30 + rs*2.0)
        if regime == "RISK_OFF": score += (-8 if rs < 0 else 4)
        ranked.append((score,a))
    leaders=[a for _,a in sorted(ranked,key=lambda x:x[0],reverse=True)[:5]]
    laggards=[a for _,a in sorted(ranked,key=lambda x:x[0])[:5]]
    return {"market_regime":regime,"btc_trend_score":btc_trend,"btc_flow_proxy_score":btc_flow,"leaders": [a.get("symbol") for a in leaders],"laggards":[a.get("symbol") for a in laggards],"reader_model":"When BTC is weak, prefer relative-strength leaders for watchlists and relative underperformers for conditional downside analysis; do not state that a coin will pump solely because BTC falls."}


def main():
    market=load(MARKET); news=load(NEWS); pre=load(PREFLIGHT); selected=pre.get("selected_opportunity") or {}
    symbols=candidates_from_market(market)
    for major in MAJORS:
        if major not in symbols: symbols.insert(0,major)
    symbols=symbols[:MAX_ASSETS]
    assets=[]
    for s in symbols:
        try:
            assets.append(build_asset(market,s))
        except Exception as exc:
            assets.append({"symbol":sym(s),"trade_setup":{"side":"WAIT","trigger":None,"invalidation":None,"tp1":None,"tp2":None},"data_quality":{"fatal_error":type(exc).__name__},"epistemic_status":"INSUFFICIENT_DATA"})
    apply_relative_strength(assets)
    rotation=rotation_map(assets)
    tradeable=[a for a in assets if (a.get("trade_setup") or {}).get("side") in {"LONG","SHORT"}]
    tradeable.sort(key=lambda a:num((a.get("multitimeframe") or {}).get("confidence")),reverse=True)
    state={"version":"23.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY" if assets else "NO_DATA","method":"Binance spot multi-timeframe OHLCV + taker-buy proxy + Binance futures OI/funding/taker/long-short proxies + BTC-relative rotation","symbols_scanned":[a.get("symbol") for a in assets],"majors":["BTC","ETH","BNB"],"selected_story_symbol":sym(selected.get("symbol")),"market_rotation":rotation,"assets":assets,"top_conditional_setups":tradeable[:6],"research_policy":["Money flow is inferred from observable proxies, not wallet-level capital tracking.","Direction is conditional, never certain.","LONG/SHORT setups require multi-timeframe alignment, flow confirmation, liquidity and model confidence.","Trigger/invalidation/TP are ATR-derived model levels, not guarantees or instructions to execute.","WAIT is a first-class answer whenever evidence conflicts or data is incomplete.","Never claim a coin will pump just because BTC falls; require relative strength and flow evidence."],"content_recipe":{"headline":"Lead with the market-regime change or capital-rotation observation, not a generic price move.","body":"Explain BTC/ETH/BNB regime, then show the alt that is gaining/losing relative strength and the evidence stack.","setup":"Only publish a conditional setup when side is LONG/SHORT and confidence >= 65, liquidity >= 55, and data quality is acceptable.","risk":"Always show invalidation and explain what would make the thesis wrong.","monetization":"Use only natural, story-relevant cashtags and verified trading widgets. Never manufacture urgency or solicit trades just to generate clicks."},"news_snapshot_used":bool(news.get("articles"))}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"23.0","generated_at":state["generated_at"],"market_rotation":rotation,"scanned":len(assets),"tradeable_setups":len(tradeable),"top_setups":[{k:v for k,v in {"symbol":a.get("symbol"),"side":(a.get("trade_setup") or {}).get("side"),"confidence":(a.get("multitimeframe") or {}).get("confidence"),"relative_strength_to_btc":a.get("relative_strength_to_btc"),"flow_proxy_score":(a.get("multitimeframe") or {}).get("flow_proxy_score")} .items()} for a in tradeable[:6]]},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":state["status"],"version":"23.0","market_regime":rotation["market_regime"],"symbols_scanned":len(assets),"top_trade_setups":[{ "symbol":a.get("symbol"),"side":(a.get("trade_setup") or {}).get("side"),"confidence":(a.get("multitimeframe") or {}).get("confidence") } for a in tradeable[:6]],"btc_flow_proxy_score":rotation["btc_flow_proxy_score"]},indent=2))

if __name__ == "__main__": main()
