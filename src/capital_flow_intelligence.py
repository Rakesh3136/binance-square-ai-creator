"""Capital-flow rotation intelligence for the existing Creator pipeline.

Uses only public Binance Spot observations. This is a content-research signal,
not a guarantee or trading advice. It ranks relative flow/strength evidence
across BTC, ETH and liquid USDT assets and produces a frozen-friendly signal
for downstream opportunity selection.
"""
from __future__ import annotations
import json, math, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/capital_flow_intelligence.json"
BASES = ["https://data-api.binance.vision", "https://api-gcp.binance.com", "https://api1.binance.com"]


def get_json(path: str, params: dict) -> object:
    query = urllib.parse.urlencode(params)
    last = None
    for base in BASES:
        try:
            req = urllib.request.Request(base + path + "?" + query, headers={"User-Agent":"binance-square-ai-creator/capital-flow"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last = exc
    raise RuntimeError(str(last))


def num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def candles(symbol: str) -> list[list]:
    return get_json("/api/v3/klines", {"symbol": symbol, "interval":"1h", "limit":24})


def signal(symbol: str) -> dict | None:
    try:
        rows = candles(symbol)
    except Exception:
        return None
    if len(rows) < 12:
        return None
    closes = [num(r[4]) for r in rows]
    vols = [num(r[5]) for r in rows]
    if not closes or closes[-12] <= 0:
        return None
    ret_12h = (closes[-1] / closes[-12] - 1.0) * 100
    ret_6h = (closes[-1] / closes[-7] - 1.0) * 100
    recent_vol = sum(vols[-6:]) / 6
    prior_vol = sum(vols[-18:-6]) / 12
    volume_ratio = recent_vol / prior_vol if prior_vol > 0 else 1.0
    # Directional pressure proxy: signed hourly returns weighted by volume.
    pressure = 0.0
    denom = 0.0
    for i in range(1, len(rows)):
        r = (closes[i] / closes[i-1] - 1.0) * 100 if closes[i-1] else 0.0
        v = vols[i]
        pressure += r * v
        denom += v
    pressure_pct = pressure / denom if denom else 0.0
    score = ret_12h * 3 + ret_6h * 2 + max(-2, min(2, volume_ratio - 1)) * 8 + pressure_pct * 4
    return {"symbol":symbol,"return_6h_pct":round(ret_6h,4),"return_12h_pct":round(ret_12h,4),"volume_ratio_6h_vs_prior_12h":round(volume_ratio,4),"volume_pressure_pct":round(pressure_pct,5),"flow_score":round(score,4)}


def main() -> int:
    tickers = get_json("/api/v3/ticker/24hr", {"type":"FULL"})
    rows=[]
    for item in tickers if isinstance(tickers,list) else []:
        s=str(item.get("symbol") or "")
        if not s.endswith("USDT"): continue
        qv=num(item.get("quoteVolume"))
        if qv < 5_000_000: continue
        x=signal(s)
        if x:
            x["quote_volume_usdt"]=round(qv,2)
            rows.append(x)
    rows.sort(key=lambda x:x["flow_score"], reverse=True)
    top=rows[:15]
    bottom=sorted(rows,key=lambda x:x["flow_score"])[:15]
    leaders=top[:5]
    laggards=bottom[:5]
    # Rotation is framed as relative strength, never as certainty about future price.
    rotation = "RISK_ON_ROTATION" if leaders and sum(x["flow_score"] for x in leaders)>0 else "RISK_OFF_OR_DEFENSIVE"
    if leaders and laggards:
        spread=sum(x["flow_score"] for x in leaders)/len(leaders)-sum(x["flow_score"] for x in laggards)/len(laggards)
    else: spread=0.0
    result={"version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"source":"Binance Spot 24h ticker + 1h OHLCV","method":"relative strength + volume acceleration + volume-weighted directional pressure","rotation_state":rotation,"leader_laggard_spread":round(spread,4),"leaders":leaders,"laggards":laggards,"highest_conviction":leaders[0] if leaders else None,"constraints":["observational signal only","no guaranteed pump/short claim","no synthetic data","requires editorial and technical gates before publication"]}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"OK","assets_scored":len(rows),"rotation_state":rotation,"highest_conviction":result["highest_conviction"]},indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
