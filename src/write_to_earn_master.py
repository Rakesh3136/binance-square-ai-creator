"""Write-to-Earn Master: deterministic monetization readiness layer.
Uses official program mechanics as publication-time constraints. Never predicts earnings, manipulates clicks, or treats engagement as revenue.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/"data/live/publication_payload.json"; CONTEXT=ROOT/"data/live/publication_context.json"
ELIG=ROOT/"data/live/write_to_earn_eligibility.json"; OUT=ROOT/"data/live/write_to_earn_master.json"
REPORT=ROOT/"data/intelligence/write_to_earn_master_report.json"
def load(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}
def main():
    payload=load(PAYLOAD); context=load(CONTEXT); elig=load(ELIG)
    text=str(payload.get("text") or "")
    category=str(context.get("category") or payload.get("category") or "").lower()
    symbol=str(payload.get("symbol") or context.get("symbol") or "").upper().replace("USDT","").replace("$","").strip()
    cashtag=bool(symbol and re.search(r"(?<![A-Za-z0-9_])\$"+re.escape(symbol)+r"(?![A-Za-z0-9_])",text,re.I))
    quiz_red_packet=bool(re.search(r"quiz\s+red\s+packet|red\s+packet\s+quiz",text,re.I))
    spam_signals=len(re.findall(r"(?:follow\s+me|like\s+and\s+share|guaranteed|100x|free\s+money)",text,re.I))
    widget=context.get("trading_widget") or payload.get("trading_widget") or payload.get("widget") or {}
    verified_widget=isinstance(widget,dict) and widget.get("verified") is True and bool(widget.get("symbol") or widget.get("id"))
    blockers=[]
    if elig.get("eligible") is not True: blockers.append(str(elig.get("reason") or "upstream_wte_gate_blocked"))
    if quiz_red_packet: blockers.append("quiz_red_packet_content")
    if spam_signals>=3: blockers.append("spam_like_repetition_signals")
    result={"generated_at":datetime.now(timezone.utc).isoformat(),"version":"WTE-MASTER-1.0","status":"READY" if not blockers else "BLOCKED","eligible":not blockers,"symbol":symbol,"cashtag_present":cashtag,"verified_widget":verified_widget,"blockers":blockers,
      "official_mechanics":{"qualification_requires_eligible_content_and_platform_rules":True,"cashtag_or_trading_widget_is_required_for_market_attribution":True,"reader_trade_must_occur_after_eligible_interaction":True,"revenue_must_never_be_inferred":True,"duplicate_or_similar_content_must_not_be_forced":True,"top_creator_bonus_is_outcome_based_not_guaranteed":True},
      "optimization_policy":{"optimize_for_reader_value_and_clear_coin_attribution":True,"never_force_a_trade":True,"never_use_fake_urgency_or_guaranteed_returns":True,"never_manipulate_clicks":True,"never_bypass_quality_or_signal_gates":True}}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"WTE-MASTER-1.0","status":result["status"],"generated_at":result["generated_at"],"blockers":blockers},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if blockers: raise SystemExit(2)
if __name__=="__main__": main()
