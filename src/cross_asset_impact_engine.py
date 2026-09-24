"""Evidence-first cross-asset impact engine.

Consumes the macro intelligence snapshot plus available market/flow snapshots.
It creates a bounded impact map for editorial routing. It never invents prices,
trade levels, or a universally 'safe' asset.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MACRO=ROOT/'data/live/global_macro_intelligence.json'
MARKET=ROOT/'data/live/market_snapshot.json'
FLOW=ROOT/'data/live/capital_flow_intelligence.json'
OUT=ROOT/'data/live/cross_asset_impact.json'
REPORT=ROOT/'data/intelligence/cross_asset_impact_report.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}

def num(x):
    try:return float(x)
    except Exception:return None

def extract_assets(x):
    out={}
    for key in ('assets','symbols','markets','rows','data','ranked'):
        v=x.get(key) if isinstance(x,dict) else None
        if isinstance(v,list):
            for row in v:
                if isinstance(row,dict):
                    s=str(row.get('symbol') or row.get('asset') or row.get('ticker') or '').upper()
                    if s: out[s]=row
    return out

def main():
    macro,market,flow=load(MACRO),load(MARKET),load(FLOW)
    theme=str(macro.get('primary_theme') or 'none')
    watch=macro.get('cross_asset_watchlist') or []
    assets=extract_assets(market); flows=extract_assets(flow)
    crypto=[]
    for symbol,row in assets.items():
        if not any(q in symbol for q in ('USDT','USDC','BTC','ETH')): continue
        crypto.append({'symbol':symbol,'price_change':num(row.get('price_change') or row.get('change_pct') or row.get('change_24h')),'volume_change':num(row.get('volume_change') or row.get('volume_change_pct'))})
    # Only rank assets when measurable fields are present; otherwise leave them unknown.
    measured=[x for x in crypto if x['price_change'] is not None or x['volume_change'] is not None]
    positive=sorted([x for x in measured if x.get('price_change') is not None],key=lambda x:x['price_change'],reverse=True)[:10]
    negative=sorted([x for x in measured if x.get('price_change') is not None],key=lambda x:x['price_change'])[:10]
    result={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY' if macro.get('event_count',0) else 'NO_MACRO_EVENT','macro_theme':theme,'event_count':macro.get('event_count',0),'cross_asset_watchlist':watch,'crypto_market_measurements':measured[:100],'relative_strength_candidates':positive,'relative_weakness_candidates':negative,'impact_chain':['verified macro event','cross-asset context','measured crypto reaction','capital-flow confirmation','signal-contract validation'],'scenario_policy':{'base':'Describe the observed reaction and evidence.','bull':'Only if measured crypto strength and supporting flow agree.','bear':'Only if measured crypto weakness and supporting flow agree.','invalidated':'Do not publish a directional setup when evidence conflicts or is stale.'},'safe_asset_policy':'No universal safest-asset claim; compare resilience, volatility and liquidity when data exists.','trade_policy':'This engine does not create entry, TP or SL. Downstream verified signal gates remain authoritative.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); REPORT.write_text(json.dumps({'version':'1.0','status':result['status'],'macro_theme':theme,'event_count':result['event_count'],'measured_assets':len(measured)},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'macro_theme':theme,'measured_assets':len(measured)}))
if __name__=='__main__':main()
