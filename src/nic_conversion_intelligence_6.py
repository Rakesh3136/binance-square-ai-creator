"""NIC Conversion Intelligence 6.0.

Defines a truthful reader-value -> asset-interaction contract. It does not
simulate clicks, infer trades, or treat engagement as revenue.
"""
from __future__ import annotations
import json, re, os
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
CONTRACT=LIVE/"nic_monetization_contract.json"
DRAFT=Path(os.getenv("DRAFT_PATH",""))
OUT=LIVE/"nic_conversion_contract.json"

def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}

def draft_path():
    if DRAFT and DRAFT.exists(): return DRAFT
    reports=sorted((ROOT/"data/reports").glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not reports: raise SystemExit("NIC conversion: no draft")
    return reports[0]

def symbol_from(contract,draft):
    for x in (contract.get("asset"),draft.get("asset"),draft.get("symbol")):
        s=re.sub(r"[^A-Z0-9]","",str(x or "").upper().replace("USDT",""))
        if re.fullmatch(r"[A-Z0-9]{1,15}",s): return s
    return ""

def main():
    contract=load(CONTRACT); report=load(draft_path())
    draft=report.get("draft") if isinstance(report.get("draft"),dict) else report
    text=str(draft.get("post") or draft.get("text") or "").strip()
    asset=symbol_from(contract,draft)
    lane=str(contract.get("content_lane") or draft.get("content_lane") or "market_setup")
    payoff=str(contract.get("reader_payoff_type") or draft.get("reader_payoff_type") or "understand")
    if not text: raise SystemExit("NIC conversion: empty reader content")
    if not asset: raise SystemExit("NIC conversion: authoritative asset missing")
    cashtag="$"+asset
    has_asset_ref=bool(re.search(r"\$"+re.escape(asset)+r"\b",text,re.I))
    action_verbs=bool(re.search(r"\b(inspect|check|compare|watch|verify|track|review|monitor|see|look)\b",text,re.I))
    trade_pressure=bool(re.search(r"\b(buy now|sell now|guaranteed|guarantee|100%|can't lose|must buy|must sell|urgent)\b",text,re.I))
    payoff_map={
      "confirmation_rule":"inspect the asset to test the stated confirmation rule",
      "data_relationship":"inspect the asset/data relationship described in the post",
      "mechanism_explanation":"inspect the affected asset to follow the described mechanism",
      "tradeoff_framework":"compare the referenced assets using the stated evidence",
      "falsification_test":"check the asset for the evidence that would falsify the thesis",
      "what_changed":"review the asset against the prior thesis and the new evidence",
      "next_test":"monitor the asset for the next measurable test",
    }
    intended=payoff_map.get(payoff,"inspect the asset to verify the evidence discussed")
    result={
      "version":"6.0","status":"PASS" if has_asset_ref and action_verbs and not trade_pressure else "BLOCK",
      "checked_at":datetime.now(timezone.utc).isoformat(),"asset":asset,"cashtag":cashtag,
      "content_lane":lane,"reader_payoff_type":payoff,"intended_reader_action":intended,
      "evidence":{
        "asset_reference_present":has_asset_ref,
        "action_reason_present":action_verbs,
        "trade_pressure_detected":trade_pressure,
        "reader_interaction_is_not_inferred":True,
        "views_are_not_revenue":True,
        "verified_reward_required":True,
      },
      "contract":{
        "interaction_goal":"reader_inspection_of_relevant_asset_surface",
        "cashtag_is_contextual_bridge":True,
        "no_fake_urgency":True,"no_trade_guarantee":True,
        "no_synthetic_clicks_or_trades":True,
      }
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if result["status"]!="PASS": raise SystemExit("NIC conversion gate: reader-action contract failed")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
