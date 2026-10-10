"""NIC 22.3 publication alignment guard.

Trade/setup drafts must match a fresh, confirmed NIC 22.3 candidate exactly.
This is a final consistency guard, not a substitute for the downstream gates.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT / "data/live"
OUT=LIVE / "nic22_3_publication_alignment.json"
TRADE_LANES={"technical_setup","high_volatility","top_gainers","top_losers",
 "capital_flow_long","capital_flow_short","flow","conditional_trade",
 "creator_signal_outcome","follow_up","next_gainer_candidate","next_loser_candidate"}

def load(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}

def norm_symbol(value):
    s=str(value or "").upper().replace("BINANCE:","").replace("$","").strip()
    if s.endswith("USDT"): s=s[:-4]
    return s

def parse_time(value):
    try:
        d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except Exception:
        return None

def evaluate(category_values, symbols, confirmation, now=None):
    now=now or datetime.now(timezone.utc)
    lanes=[str(x or "").strip().lower().replace(" ","_") for x in category_values]
    lane=next((x for x in lanes if x in TRADE_LANES), "")
    symbol=next((norm_symbol(x) for x in symbols if norm_symbol(x)), "")
    if not lane:
        return {"version":"1.0","status":"PASS_NON_TRADE_LANE","allowed":True,
                "reason":"draft_not_classified_as_trade_setup","category":next((x for x in lanes if x),""),"symbol":symbol or None}
    selected=confirmation.get("selected_opportunity") if isinstance(confirmation.get("selected_opportunity"),dict) else {}
    confirmed_symbol=norm_symbol(selected.get("symbol") or selected.get("topic"))
    stamp=parse_time(confirmation.get("generated_at"))
    age=None if stamp is None else (now-stamp).total_seconds()/60
    fresh=age is not None and 0 <= age <= 90
    valid=(str(confirmation.get("status") or "").upper()=="CONFIRMED"
           and str(selected.get("confirmation_status") or "").upper()=="CONFIRMED_EARLY_SETUP"
           and bool(symbol) and symbol==confirmed_symbol and fresh)
    return {"version":"1.0","status":"PASS_MATCHED_CONFIRMATION" if valid else "BLOCKED_MISSING_OR_MISMATCHED_CONFIRMATION",
        "allowed":valid,"category":lane,"symbol":symbol or None,"confirmed_symbol":confirmed_symbol or None,
        "confirmation_status":confirmation.get("status"),"confirmation_age_minutes":round(age,2) if age is not None else None,
        "confirmation_fresh":fresh,"reason":"trade_setup_matches_fresh_NIC22.3_confirmation" if valid else
        "trade_setup_requires_fresh_same_symbol_NIC22.3_confirmation",
        "policy":"This guard only enforces evidence alignment; all existing market, editorial, chart and publication gates remain mandatory."}

def main():
    frozen=load(LIVE/"authoritative_opportunity.json")
    context=load(LIVE/"publication_context.json")
    pre=load(LIVE/"editorial_preflight.json")
    selected=pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"),dict) else {}
    draft_path=Path(os.environ["DRAFT_PATH"]) if os.environ.get("DRAFT_PATH") else None
    report=load(draft_path) if draft_path and draft_path.exists() else {}
    draft=report.get("draft") if isinstance(report.get("draft"),dict) else report
    categories=[frozen.get("category"),frozen.get("lane"),context.get("category"),context.get("lane"),
                selected.get("category"),selected.get("lane"),draft.get("category"),draft.get("lane")]
    symbols=[frozen.get("symbol"),context.get("symbol"),selected.get("symbol"),selected.get("topic"),
             draft.get("symbol"),draft.get("topic"),draft.get("asset")]
    confirmation=load(LIVE/"nic22_3_confirmation_selection.json")
    result=evaluate(categories,symbols,confirmation)
    result["generated_at"]=datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if not result["allowed"]:
        # Reuse the established no-publication contract so the workflow handles
        # this as a valid safety stop rather than a broken run.
        entry={"version":"24.3.1-alignment-stop","status":"BLOCKED","publish":False,
               "reason":"NIC 22.3 confirmation alignment failed; trade/setup draft cannot publish.",
               "symbol":result.get("symbol"),"failures":[result["reason"]],"alignment":result}
        (LIVE/"nic24_3_early_entry_gate.json").write_text(json.dumps(entry,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        raise SystemExit(24)

if __name__=="__main__":
    main()
