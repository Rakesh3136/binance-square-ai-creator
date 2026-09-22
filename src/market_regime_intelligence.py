"""Deterministic market-regime evidence layer for the autonomous creator."""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/"data/live/market_snapshot.json"
FLOW=ROOT/"data/live/capital_flow_intelligence.json"
OUT=ROOT/"data/live/market_regime_intelligence.json"

def load(p):
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except Exception:return {}

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def main():
    market,flow=load(MARKET),load(FLOW)
    rows=[]
    for key in ("top_content_signals","top_gainers","top_losers","highest_volume"):
        rows += [x for x in market.get(key,[]) if isinstance(x,dict)]
    changes=[num(x.get("price_change_6h_pct",x.get("price_change_percent"))) for x in rows]
    changes=[x for x in changes if x is not None]
    volumes=[num(x.get("quote_volume_usdt",x.get("quote_volume"))) for x in rows]
    volumes=[x for x in volumes if x is not None and x>0]
    avg=sum(changes)/len(changes) if changes else 0.0
    dispersion=(sum((x-avg)**2 for x in changes)/len(changes))**0.5 if changes else 0.0
    movers=sum(1 for x in changes if abs(x)>=2.0)
    positive=sum(1 for x in changes if x>1.0)
    negative=sum(1 for x in changes if x<-1.0)
    flow_setups=flow.get("top_conditional_setups") or []
    flow_count=sum(1 for x in flow_setups if isinstance(x,dict))
    if not changes:
        regime="UNKNOWN"; confidence="LOW"; reason="Insufficient verified market observations."
    elif positive>=max(3,negative*2) and avg>1.0:
        regime="BROAD_RISK_ON"; confidence="MEDIUM"; reason="Positive breadth and positive average move dominate the available universe."
    elif negative>=max(3,positive*2) and avg<-1.0:
        regime="BROAD_RISK_OFF"; confidence="MEDIUM"; reason="Negative breadth and negative average move dominate the available universe."
    elif movers>=3 and dispersion>=2.5:
        regime="HIGH_DISPERSION"; confidence="MEDIUM"; reason="Large cross-asset dispersion indicates selective rather than uniform conditions."
    elif dispersion<1.0:
        regime="LOW_DISPERSION"; confidence="MEDIUM"; reason="Observed assets are moving relatively close together."
    else:
        regime="MIXED"; confidence="LOW"; reason="Evidence does not support a stronger regime classification."
    result={
      "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
      "regime":regime,"confidence":confidence,"reason":reason,
      "evidence":{"observations":len(changes),"average_6h_change_pct":round(avg,4),"dispersion_pct":round(dispersion,4),"positive_movers":positive,"negative_movers":negative,"large_movers":movers,"conditional_flow_setups":flow_count,"volume_observations":len(volumes)},
      "policy":{"descriptive_only":True,"never_overrides_frozen_contract":True,"never_invents_signal":True}
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
