"""Pre-router intelligence shortlist: broaden discovery without granting publication authority.
This layer ranks/filters candidate symbols using already-produced evidence. It never
creates a trade contract, never publishes, and never overrides Signal-First gates.
"""
from __future__ import annotations
import json, math, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/"data/live/market_snapshot.json"
FLOW=ROOT/"data/live/capital_flow_intelligence.json"
FULL=ROOT/"data/live/full_universe_flow.json"
RANK=ROOT/"data/live/opportunity_ranking_6.json"
REGIME=ROOT/"data/live/market_regime_intelligence.json"
MESH=ROOT/"data/live/agent_mesh_300.json"
OUT=ROOT/"data/live/pre_router_intelligence.json"

def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:
        return {}

def num(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else 0.0
    except Exception:
        return 0.0

BINANCE_BASES=(
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
)

def live_usdt_bases():
    # Best-effort current Binance Spot TRADING universe for discovery filtering.
    # The final router remains authoritative and re-verifies independently.
    for base in BINANCE_BASES:
        try:
            req=urllib.request.Request(
                base+"/api/v3/exchangeInfo?symbolStatus=TRADING",
                headers={"User-Agent":"binance-square-ai-creator/pre-router","Accept":"application/json"},
            )
            with urllib.request.urlopen(req,timeout=15) as h:
                data=json.loads(h.read().decode("utf-8"))
            return {str(x.get("symbol","")).upper()[:-4] for x in data.get("symbols",[])
                    if str(x.get("status","")).upper()=="TRADING" and str(x.get("symbol","")).upper().endswith("USDT")}
        except Exception:
            continue
    return set()

def add(pool,x,source):
    if not isinstance(x,dict): return
    symbol=str(x.get("symbol") or "").upper().replace("USDT","").replace("BINANCE:","").strip()
    if not symbol: return
    score=max(
        num(x.get("score")),
        num(x.get("ranker_score")),
        num(x.get("discovery_score")),
        num(x.get("flow_confidence")),
        num(x.get("flow_score")),
        num(x.get("content_signal_score")),
    )
    row=pool.setdefault(symbol,{"symbol":symbol,"sources":[],"evidence_score":0.0})
    row["evidence_score"]=max(row["evidence_score"],score)
    if source not in row["sources"]: row["sources"].append(source)
    for key in ("price_change_6h_pct","price_change_percent","flow_state","category","lane","type"):
        if key in x and key not in row: row[key]=x[key]

def main():
    market,flow,full,rank,regime,mesh=(load(p) for p in (MARKET,FLOW,FULL,RANK,REGIME,MESH))
    pool={}
    for key in ("top_content_signals","top_gainers","top_losers","highest_volume","new_listing_market"):
        for x in market.get(key) or []: add(pool,x,"market_snapshot")
    for key in ("top_conditional_setups","top_flow_signals"):
        for x in flow.get(key) or []: add(pool,x,"capital_flow")
    for x in full.get("early_movers") or []: add(pool,x,"full_universe_flow")
    for key in ("selected","top_candidates"):
        value=rank.get(key)
        if isinstance(value,dict): add(pool,value,"opportunity_ranking")
        elif isinstance(value,list):
            for x in value: add(pool,x,"opportunity_ranking")
    mesh_top=mesh.get("top") if isinstance(mesh,dict) else []
    for x in mesh_top or []: add(pool,x,"agent_mesh_300")

    regime_name=str(regime.get("regime") or "UNKNOWN").upper()
    live_symbols=live_usdt_bases()
    ranked=[]
    for row in pool.values():
        # Filter stale symbols when a live Binance universe is available.
        # Final router verification remains authoritative.
        if live_symbols and row["symbol"] not in live_symbols:
            continue
        sources=len(row["sources"])
        # This is discovery prioritization only. No direction or trade levels are invented.
        support=min(25.0,sources*5.0)
        regime_bonus=5.0 if regime_name in {"BROAD_RISK_ON","BROAD_RISK_OFF"} else 0.0
        row["pre_router_priority"]=round(min(100.0,row["evidence_score"]+support+regime_bonus),2)
        row["regime_context"]=regime_name
        ranked.append(row)
    ranked.sort(key=lambda x:(x["pre_router_priority"],len(x["sources"])),reverse=True)
    result={
        "version":"1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY",
        "candidate_count":len(ranked),
        "source_candidate_count":len(pool),
        "live_symbol_filter_active":bool(live_symbols),
        "shortlist":ranked[:40],
        "regime":regime_name,
        "mesh_version":mesh.get("version") if isinstance(mesh,dict) else None,
        "policy":{
            "discovery_only":True,
            "does_not_create_trade_contract":True,
            "does_not_override_router":True,
            "does_not_publish":True,
            "router_must_reverify_live_symbol_and_ohlcv":True,
        },
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","candidate_count":len(ranked),"source_candidate_count":len(pool),"live_symbol_filter_active":bool(live_symbols),"shortlist":[x["symbol"] for x in ranked[:10]],"regime":regime_name},ensure_ascii=False))
if __name__=="__main__":
    main()
