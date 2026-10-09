"""NIC 24.3 — Early-entry and post-extension publication gate."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
OUT=LIVE/"nic24_3_early_entry_gate.json"
TRADE_LANES={"technical_setup","high_volatility","top_gainers","top_losers","capital_flow_long","capital_flow_short","flow","conditional_trade","creator_signal_outcome","follow_up"}
MAX_ABS_24H_MOVE_PCT=5.0
MAX_MARKET_AGE_MINUTES=15.0

def load(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}

def symbol(value):
    s=str(value or "").upper().replace("BINANCE:","").replace("$","").strip()
    return s[:-4] if s.endswith("USDT") else s

def parse_time(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        return None

def evaluate(category, market_move, market_age_minutes, asset_found=True):
    lane=str(category or "").strip().lower().replace(" ","_")
    if lane not in TRADE_LANES:
        return {"status":"PASS","publish":True,"reason":"non_trade_editorial_lane","category":lane}
    failures=[]
    if not asset_found or market_move is None:
        failures.append("missing_asset_market_move")
    if market_age_minutes is None or market_age_minutes < 0 or market_age_minutes > MAX_MARKET_AGE_MINUTES:
        failures.append("missing_or_stale_market_snapshot")
    if market_move is not None and abs(float(market_move)) > MAX_ABS_24H_MOVE_PCT:
        failures.append("asset_already_extended_for_new_entry")
    return {"status":"BLOCKED" if failures else "PASS","publish":not failures,"category":lane,
            "market_move_24h_pct":market_move,"market_age_minutes":market_age_minutes,
            "thresholds":{"max_abs_24h_move_pct":MAX_ABS_24H_MOVE_PCT,"max_market_age_minutes":MAX_MARKET_AGE_MINUTES},
            "failures":failures,
            "reason":"New setup blocked: entry may be late or current market evidence is insufficient." if failures else "Asset remains within the configured extension threshold and market data is fresh.",
            "policy":"A passing gate does not predict direction or guarantee profit."}

def main():
    now=datetime.now(timezone.utc)
    frozen=load(LIVE/"authoritative_opportunity.json"); context=load(LIVE/"publication_context.json")
    pre=load(LIVE/"editorial_preflight.json"); market=load(LIVE/"market_snapshot.json")
    selected=pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"),dict) else {}
    report_path=Path(os.environ["DRAFT_PATH"]) if os.environ.get("DRAFT_PATH") else None
    report=load(report_path) if report_path and report_path.exists() else {}
    draft=report.get("draft") if isinstance(report.get("draft"),dict) else {}
    category=str(frozen.get("category") or context.get("category") or selected.get("category") or draft.get("category") or "").lower()
    asset=symbol(frozen.get("symbol") or context.get("symbol") or selected.get("symbol") or draft.get("symbol"))
    move=None; found=False
    for group in ("top_content_signals","top_gainers","top_losers","highest_volume","new_listing_market","early_movers"):
        for row in (market.get(group) if isinstance(market.get(group),list) else []):
            if not isinstance(row,dict) or symbol(row.get("symbol") or row.get("symbol_usdt"))!=asset: continue
            found=True
            try: move=float(row.get("price_change_percent"))
            except (TypeError,ValueError): move=None
            break
        if found: break
    stamp=parse_time(market.get("generated_at") or market.get("timestamp") or market.get("updated_at"))
    age=None if stamp is None else (now-stamp).total_seconds()/60.0
    result=evaluate(category,move,age,found)
    result.update({"version":"24.3.0","generated_at":now.isoformat(),"symbol":asset or None,"source":"data/live/market_snapshot.json"})
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result["publish"] is not True: raise SystemExit(24)

if __name__=="__main__": main()
