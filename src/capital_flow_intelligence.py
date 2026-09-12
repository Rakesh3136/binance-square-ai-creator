"""Capital-flow rotation intelligence for the existing Creator pipeline.

Uses public Binance Spot observations as a market-flow proxy. Produces
conditional LONG/SHORT prediction setups with explicit trigger, TP1, TP2,
SL/invalidation and confidence for downstream publication and outcome tracking.
"""
from __future__ import annotations
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/capital_flow_intelligence.json"
BASES = ["https://data-api.binance.vision", "https://api-gcp.binance.com", "https://api1.binance.com"]
MAX_ASSETS = 80
MIN_QUOTE_VOLUME = 5_000_000

def get_json(path: str, params: dict) -> object:
    query = urllib.parse.urlencode(params); last = None
    for base in BASES:
        try:
            req = urllib.request.Request(base + path + "?" + query, headers={"User-Agent": "binance-square-ai-creator/capital-flow"})
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc: last = exc
    raise RuntimeError(str(last))

def num(value, default=0.0):
    try:
        result = float(value); return result if math.isfinite(result) else default
    except (TypeError, ValueError): return default

def candles(symbol: str) -> list[list]:
    data = get_json("/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": 24})
    return data if isinstance(data, list) else []

def signal(symbol: str) -> dict | None:
    try: rows = candles(symbol)
    except Exception: return None
    if len(rows) < 18: return None
    closes=[num(r[4]) for r in rows]; highs=[num(r[2]) for r in rows]; lows=[num(r[3]) for r in rows]; vols=[num(r[5]) for r in rows]
    if closes[-12] <= 0 or closes[-1] <= 0: return None
    ret_12h=(closes[-1]/closes[-12]-1)*100; ret_6h=(closes[-1]/closes[-7]-1)*100
    recent_vol=sum(vols[-6:])/6; prior_vol=sum(vols[-18:-6])/12; volume_ratio=recent_vol/prior_vol if prior_vol else 1
    pressure=0; denom=0
    for i in range(1,len(rows)):
        previous=closes[i-1]; move=(closes[i]/previous-1)*100 if previous else 0; pressure += move*vols[i]; denom += vols[i]
    pressure_pct=pressure/denom if denom else 0
    score=ret_12h*3+ret_6h*2+max(-2,min(2,volume_ratio-1))*8+pressure_pct*4
    return {"symbol":symbol,"last_price":round(closes[-1],10),"recent_6h_high":round(max(highs[-6:]),10),"recent_6h_low":round(min(lows[-6:]),10),"return_6h_pct":round(ret_6h,4),"return_12h_pct":round(ret_12h,4),"volume_ratio_6h_vs_prior_12h":round(volume_ratio,4),"volume_pressure_pct":round(pressure_pct,5),"flow_score":round(score,4)}

def select_assets(tickers: list[dict]) -> list[tuple[str,float]]:
    eligible=[]
    for item in tickers:
        symbol=str(item.get("symbol") or "")
        if not symbol.endswith("USDT"): continue
        q=num(item.get("quoteVolume"))
        if q < MIN_QUOTE_VOLUME: continue
        eligible.append((symbol,q,abs(num(item.get("priceChangePercent")))))
    liquidity=sorted(eligible,key=lambda x:x[1],reverse=True)[:50]; movers=sorted(eligible,key=lambda x:x[2],reverse=True)[:30]
    merged={}
    for symbol,q,_ in liquidity+movers: merged[symbol]=q
    for symbol in ("BTCUSDT","ETHUSDT","BNBUSDT"):
        for candidate,q,_ in eligible:
            if candidate==symbol: merged[symbol]=q; break
    return list(merged.items())[:MAX_ASSETS]

def build_conditional_setups(rows: list[dict]) -> list[dict]:
    setups=[]
    for item in rows:
        score=num(item.get("flow_score")); vr=num(item.get("volume_ratio_6h_vs_prior_12h")); ret=num(item.get("return_6h_pct")); last=num(item.get("last_price")); high=num(item.get("recent_6h_high")); low=num(item.get("recent_6h_low"))
        if not last or not high or not low or high<=low or vr<1.15: continue
        if score>=8 and ret>0: side="LONG"; trigger=high*1.001; invalidation=low
        elif score<=-8 and ret<0: side="SHORT"; trigger=low*0.999; invalidation=high
        else: continue
        risk=abs(trigger-invalidation)
        if risk<=0: continue
        tp1=trigger+risk*1.0 if side=="LONG" else trigger-risk*1.0
        tp2=trigger+risk*1.5 if side=="LONG" else trigger-risk*1.5
        confidence=min(95.0,65.0+min(20.0,abs(score)*0.8)+min(10.0,(vr-1.15)*20))
        setups.append({
            "symbol":item["symbol"],
            "flow_score":round(score,4),
            "flow_confidence":round(confidence,2),
            "prediction":{"direction":side,"entry_trigger":round(trigger,10),"tp1":round(tp1,10),"tp2":round(tp2,10),"sl":round(invalidation,10),"invalidation":round(invalidation,10),"risk_reward_tp1":1.0,"risk_reward_tp2":1.5},
            "multitimeframe":{"confidence":round(confidence,2),"flow_proxy_score":round(max(0,min(100,50+score*2.5)),2)},
            "flow_notes":["6H/12H relative strength","6H volume acceleration versus prior 12H","volume-weighted directional pressure","trigger, TP and invalidation are derived from fresh 1H candles"],
            "trade_setup":{"side":side,"trigger":round(trigger,10),"target":round(tp2,10),"tp1":round(tp1,10),"tp2":round(tp2,10),"invalidation":round(invalidation,10),"risk_reward":1.5,"conditional":True}
        })
    setups.sort(key=lambda x:num(x.get("flow_confidence")),reverse=True)
    return setups[:10]

def main()->int:
    tickers=get_json("/api/v3/ticker/24hr",{"type":"FULL"}); ticker_rows=tickers if isinstance(tickers,list) else []; selected=select_assets(ticker_rows)
    rows=[]; quote_by_symbol=dict(selected)
    for symbol,_ in selected:
        result=signal(symbol)
        if result: result["quote_volume_usdt"]=round(quote_by_symbol[symbol],2); rows.append(result)
    rows.sort(key=lambda x:x["flow_score"],reverse=True); leaders=rows[:5]; laggards=sorted(rows,key=lambda x:x["flow_score"])[:5]; setups=build_conditional_setups(rows)
    rotation="RISK_ON_ROTATION" if leaders and sum(x["flow_score"] for x in leaders)>0 else "RISK_OFF_OR_DEFENSIVE"
    spread=(sum(x["flow_score"] for x in leaders)/len(leaders)-sum(x["flow_score"] for x in laggards)/len(laggards)) if leaders and laggards else 0
    result={"version":"1.3","generated_at":datetime.now(timezone.utc).isoformat(),"source":"Binance Spot 24h ticker + 1h OHLCV","method":"relative strength + volume acceleration + volume-weighted directional pressure","assets_considered":len(selected),"assets_scored":len(rows),"rotation_state":rotation,"leader_laggard_spread":round(spread,4),"leaders":leaders,"laggards":laggards,"highest_conviction":leaders[0] if leaders else None,"top_conditional_setups":setups,"prediction_contract":{"required":["direction","entry_trigger","tp1","tp2","sl","confidence"],"tp1_rr":1.0,"tp2_rr":1.5,"conditional_only":True},"constraints":["observational signal only","capital flow is a market-data proxy, not wallet-level fund-flow data","setups are conditional on trigger; they are not guaranteed calls","targets/invalidation are derived from fresh 1H market structure","no synthetic data","requires editorial and technical gates before publication"]}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"OK","assets_considered":len(selected),"assets_scored":len(rows),"conditional_setups":len(setups),"rotation_state":rotation,"highest_conviction":result["highest_conviction"]},indent=2)); return 0

if __name__=="__main__": raise SystemExit(main())
