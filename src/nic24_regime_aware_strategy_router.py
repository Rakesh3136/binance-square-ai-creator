"""NIC 24 — Regime-aware strategy router.

Selects a research/content strategy from observable market-regime evidence.
It is deliberately advisory: it cannot create a trade, alter frozen levels,
or bypass any publication/risk gate.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
OUT=LIVE/"nic24_regime_strategy_router.json"

def load(name):
    try:
        x=json.loads((LIVE/name).read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def text(*xs): return " ".join(str(x or "").lower() for x in xs)

def classify(row):
    blob=text(row.get("market_regime"),row.get("regime"),row.get("setup_type"),row.get("setup_family"),row.get("signal_type"),row.get("trend"),row.get("volatility_state"))
    if any(k in blob for k in ("breakout","expansion","range expansion")): return "BREAKOUT_EXPANSION"
    if any(k in blob for k in ("trend","continuation","higher high","lower low")): return "TREND_CONTINUATION"
    if any(k in blob for k in ("mean reversion","reversion","oversold","overbought")): return "MEAN_REVERSION"
    if any(k in blob for k in ("momentum","impulse","acceleration")): return "MOMENTUM"
    if any(k in blob for k in ("range","sideways","chop","consolidation")): return "RANGE"
    return "UNCLASSIFIED"

def strategy(regime):
    return {
      "BREAKOUT_EXPANSION":"breakout_research",
      "TREND_CONTINUATION":"trend_continuation_research",
      "MEAN_REVERSION":"mean_reversion_research",
      "MOMENTUM":"momentum_research",
      "RANGE":"range_structure_research",
      "UNCLASSIFIED":"no_trade_research"
    }[regime]

def main():
    pred=load("nic_prediction_engine.json")
    candidates=pred.get("candidates") if isinstance(pred.get("candidates"),list) else []
    routed=[]
    for row in candidates:
        if not isinstance(row,dict): continue
        regime=classify(row)
        confidence=row.get("calibrated_confidence",row.get("model_confidence"))
        try: confidence=float(confidence)
        except (TypeError,ValueError): confidence=None
        routed.append({"symbol":str(row.get("symbol") or "").upper(),"side":str(row.get("side") or "").upper(),"regime":regime,"strategy":strategy(regime),"confidence":confidence,"strategy_state":"ROUTED" if regime!="UNCLASSIFIED" else "HOLD","reason":"regime evidence matched" if regime!="UNCLASSIFIED" else "insufficient regime evidence"})
    result={"schema":"NIC-24.0-REGIME-ROUTER","generated_at":datetime.now(timezone.utc).isoformat(),"routes":routed,"policy":["Regime routing is advisory and does not execute trades.","Unclassified conditions default to HOLD/no-trade research.","Strategy routing cannot alter frozen entry, invalidation, TP1 or TP2.","Strategy diversity must not override evidence or publication gates."]}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
