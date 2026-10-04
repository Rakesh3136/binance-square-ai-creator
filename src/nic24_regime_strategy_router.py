"""NIC 24 — Regime-aware strategy router.

Routes an already researched market opportunity into a strategy/content lane.
This is classification only: it never creates a trade, changes prices, or
bypasses risk/publication gates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data/live'
SOURCE=LIVE/'nic_prediction_engine.json'
OUT=LIVE/'nic24_regime_strategy_route.json'

TREND={'TREND','TRENDING','UPTREND','DOWNTREND'}
RANGE={'RANGE','RANGING','SIDEWAYS','MEAN_REVERSION'}
VOL={'VOLATILE','HIGH_VOLATILITY','VOLATILITY_EXPANSION','EXPANSION'}
BREAK={'BREAKOUT','PRE_BREAKOUT','SQUEEZE'}
FLOW={'CAPITAL_FLOW','FLOW','ACCUMULATION','DISTRIBUTION'}

def norm(x): return str(x or '').upper().replace('-','_').replace(' ','_')

def classify(row):
    regime=norm(row.get('market_regime') or row.get('regime'))
    setup=norm(row.get('setup_type') or row.get('setup_family'))
    evidence=row.get('evidence') if isinstance(row.get('evidence'),dict) else {}
    if regime in BREAK or setup in BREAK: lane='BREAKOUT'; reason='breakout regime/setup'
    elif regime in VOL or setup in VOL: lane='MOMENTUM_VOLATILITY'; reason='volatility expansion'
    elif regime in TREND: lane='TREND_CONTINUATION'; reason='directional regime'
    elif regime in RANGE or setup in RANGE: lane='MEAN_REVERSION_RANGE'; reason='range regime'
    elif setup in FLOW or regime in FLOW: lane='CAPITAL_FLOW'; reason='flow-driven setup'
    else: lane='RESEARCH_ONLY'; reason='regime evidence insufficient for specialized strategy'
    return lane,reason,evidence

def main():
    try: doc=json.loads(SOURCE.read_text(encoding='utf-8'))
    except Exception: doc={}
    candidates=doc.get('candidates') if isinstance(doc.get('candidates'),list) else []
    routes=[]
    for row in candidates:
        if not isinstance(row,dict): continue
        lane,reason,evidence=classify(row)
        routes.append({'symbol':str(row.get('symbol') or '').upper(),'side':norm(row.get('side')),
                       'regime':norm(row.get('market_regime') or row.get('regime')),
                       'setup_type':norm(row.get('setup_type') or row.get('setup_family')),
                       'strategy_lane':lane,'reason':reason,'evidence_keys':sorted(map(str,evidence.keys()))})
    result={'schema':'NIC-24-REGIME-ROUTER-1.0','generated_at':datetime.now(timezone.utc).isoformat(),
            'routes':routes,'policy':['Classification only; never executes trades.','Never changes entry, invalidation, TP1 or TP2.','RESEARCH_ONLY is preferred to inventing a strategy when regime evidence is weak.','Downstream authority and publication gates remain mandatory.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
