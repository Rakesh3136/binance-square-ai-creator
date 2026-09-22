"""Adversarial pre-publication thesis challenge. Evidence only; no autonomous trading override."""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUTH=ROOT/"data/live/authoritative_opportunity.json"
ROUTING=ROOT/"data/live/signal_first_routing.json"
TECH=ROOT/"data/live/technical_enrichment.json"
REGIME=ROOT/"data/live/market_regime_intelligence.json"
OUT=ROOT/"data/live/adversarial_brain_review.json"

def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,dict) else {}
    except Exception:return {}
def num(v):
    try:return float(v)
    except Exception:return None

def main():
    auth,routing,tech,regime=load(AUTH),load(ROUTING),load(TECH),load(REGIME)
    selected=routing.get("selected") if isinstance(routing.get("selected"),dict) else {}
    if not selected: selected=auth
    setup=selected.get("trade_setup") if isinstance(selected.get("trade_setup"),dict) else {}
    prediction=selected.get("prediction") if isinstance(selected.get("prediction"),dict) else {}
    side=str(setup.get("side") or prediction.get("direction") or auth.get("direction") or "").upper()
    entry=num(setup.get("trigger",prediction.get("entry_trigger",auth.get("reference_price"))))
    tp1=num(setup.get("tp1",prediction.get("tp1")))
    sl=num(setup.get("invalidation",prediction.get("sl",auth.get("invalidation"))))
    failures=[]; challenges=[]
    if side not in {"LONG","SHORT"}: failures.append("missing_direction")
    if entry is None or tp1 is None or sl is None: failures.append("incomplete_trade_contract")
    elif side=="LONG" and not sl<entry<tp1: failures.append("invalid_long_level_order")
    elif side=="SHORT" and not tp1<entry<sl: failures.append("invalid_short_level_order")
    if routing.get("prediction_contract_complete") is not True: failures.append("router_contract_not_complete")
    if selected and selected.get("signal_first_ohlcv_verified") is not True and not (selected.get("evidence") or {}).get("ohlcv_candles_used"):
        challenges.append("Signal is not carrying explicit fresh completed-candle provenance.")
    if regime.get("regime")=="HIGH_DISPERSION": challenges.append("High cross-asset dispersion: avoid treating one asset move as broad market confirmation.")
    if regime.get("regime") in {"MIXED","UNKNOWN"}: challenges.append("Market regime evidence is not strong enough for broad directional language.")
    # This is a challenge layer, not a score/ranking system.
    publish_ok=not failures
    result={
      "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
      "status":"PASS" if publish_ok else "BLOCK",
      "publish_review":publish_ok,
      "symbol":str(selected.get("symbol") or auth.get("symbol") or "").upper(),
      "direction":side,
      "challenges":challenges,"failures":failures,
      "adversarial_questions":[
        "What verified observation would falsify this thesis?",
        "Are Entry, TP1 and SL derived from the same frozen contract?",
        "Could the apparent signal be explained by broad market movement instead?",
        "Is the wording stronger than the evidence?"
      ],
      "policy":{"challenge_only":True,"never_rewrite_contract":True,"never_claim_certainty":True,"never_override_deterministic_gates":True}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
