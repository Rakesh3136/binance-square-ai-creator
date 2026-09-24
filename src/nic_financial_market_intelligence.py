"""NIC Financial Market Intelligence v1.

Keyless knowledge and evidence layer for market structure, crypto literacy,
charts, global finance, cross-asset transmission and observed liquidity.
It separates educational mechanisms from live directional decisions.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
INTEL=ROOT/"data/intelligence"
OUT=LIVE/"nic_financial_market_intelligence.json"
REPORT=INTEL/"nic_financial_market_intelligence_report.json"
MEMORY=LIVE/"nic_financial_market_memory.json"

ASSET_ONTOLOGY={
 "bitcoin":{"symbol":"BTC","role":"native crypto network asset","concepts":["scarcity","settlement","liquidity sensitivity","market beta"]},
 "ether":{"symbol":"ETH","role":"Ethereum network asset","concepts":["gas","smart contracts","staking","network activity"]},
 "stablecoins":{"role":"tokens designed to track a reference asset","concepts":["settlement","exchange liquidity","collateral","depeg risk"]},
 "altcoins":{"role":"heterogeneous cryptoassets other than BTC","concepts":["sector narratives","liquidity differences","idiosyncratic catalysts"]},
 "memecoins":{"role":"narrative/community-sensitive cryptoassets","concepts":["reflexivity","attention","high volatility","liquidity risk"]},
}

FINANCE_MAP={
 "markets":["money markets","government bonds","credit","equities","FX","commodities","real assets","crypto","derivatives"],
 "flow_channels":["bank credit and deposits","portfolio allocation","Treasury and money-market allocation","commodity trade","FX flows","exchange liquidity","on-chain liquidity"],
 "plumbing":["liquidity","collateral","leverage","funding","open interest","basis","spreads","market depth"],
}

CHART_CURRICULUM={
 "candles":["open","high","low","close","body","wick"],
 "volume":["spot volume","quote volume","relative volume","volume acceleration"],
 "trend":["higher highs","higher lows","lower highs","lower lows","moving averages"],
 "structure":["support","resistance","range","breakout","breakdown","retest","invalidation"],
 "momentum":["rate of change","RSI-style momentum","divergence as a hypothesis"],
 "volatility":["range","ATR-style range","volatility expansion","volatility compression"],
 "derivatives":["funding","open interest","basis","liquidations","mark price"],
 "risk":["entry trigger","targets","stop/invalidation","risk/reward","position sizing"],
}

MECHANISMS={
 "oil_up":{
  "event":"oil price rises",
  "channels":["higher energy input costs","transport/production cost pressure","inflation-expectation pressure in oil-sensitive economies","possible margin pressure for energy-intensive sectors","possible income transfer toward energy producers"],
  "sectors":["energy producers","airlines and transport","chemicals","manufacturing","consumer sectors","oil-importing economies","oil-exporting economies"],
  "watch":["inflation expectations","bond yields","USD","equities","gold","BTC","ETH"],
  "crypto_rule":"Oil alone does not determine BTC direction; verify rates, USD, liquidity, risk appetite and crypto relative strength."
 },
 "oil_down":{
  "event":"oil price falls",
  "channels":["lower energy input costs","potential disinflationary pressure","support for energy-consuming sectors","possible pressure on energy producers and oil-sensitive exporters"],
  "sectors":["transport","manufacturing","consumer sectors","energy producers","oil-importing economies"],
  "watch":["inflation expectations","bond yields","USD","equities","BTC"],
  "crypto_rule":"Lower oil does not automatically imply BTC strength; measure the broader macro and liquidity channel."
 },
 "rates_up":{
  "event":"policy rates or market yields rise",
  "channels":["higher financing costs","higher discount rates","potential tightening in financial conditions","possible currency support"],
  "sectors":["real estate","growth equities","leveraged businesses","banks","credit"],
  "watch":["USD","Treasuries/yields","equities","gold","BTC","ETH"],
  "crypto_rule":"Use contemporaneous evidence rather than assuming a fixed BTC response."
 },
 "rates_down":{
  "event":"policy rates or market yields fall",
  "channels":["lower financing costs","lower discount rates","potential easing in financial conditions","possible currency effects"],
  "sectors":["real estate","growth assets","credit-sensitive sectors"],
  "watch":["USD","Treasuries/yields","equities","gold","BTC","ETH"],
  "crypto_rule":"Lower yields can be supportive in some regimes, but BTC still requires current evidence."
 },
 "usd_up":{
  "event":"USD strengthens",
  "channels":["changes in dollar funding conditions","commodity repricing effects","cross-border allocation changes"],
  "sectors":["emerging markets","exporters","importers","commodities","US multinationals"],
  "watch":["Treasury yields","commodities","equities","BTC"],
  "crypto_rule":"USD/BTC relationships are regime-dependent, not permanent laws."
 },
 "risk_off":{
  "event":"broad risk appetite deteriorates",
  "channels":["de-risking","liquidity demand","portfolio rotation","higher volatility"],
  "sectors":["high-beta equities","small caps","leveraged credit","altcoins"],
  "watch":["USD","Treasuries","gold","equities","BTC","altcoins"],
  "crypto_rule":"Measure breadth and relative strength; do not treat all cryptoassets as one asset."
 },
}

def load(path,default):
 try:
  if not path.exists(): return default
  x=json.loads(path.read_text(encoding="utf-8"))
  return x if isinstance(x,type(default)) else default
 except Exception:return default

def num(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except Exception:return None

def base_symbol(v):
 s=str(v or "").upper().replace("$","").replace("BINANCE:","")
 if s.endswith("USDT"):s=s[:-4]
 return s if s.isalnum() and len(s)<=15 else ""

def extract_crypto():
 paths=[LIVE/"market_snapshot.json",LIVE/"capital_flow_intelligence.json",LIVE/"full_universe_flow.json"]
 out={}
 for path in paths:
  data=load(path,{})
  for key in ("top_content_signals","top_gainers","top_losers","highest_volume","leaders","laggards","top_flow_candidates"):
   for row in data.get(key,[]) if isinstance(data.get(key),list) else []:
    if not isinstance(row,dict):continue
    s=base_symbol(row.get("symbol") or row.get("asset") or row.get("ticker"))
    if not s:continue
    item=out.setdefault(s,{"symbol":s})
    for k in ("last_price","price_change_percent","price_change_6h_pct","quote_volume_usdt","volume_acceleration","volume_vs_24h_median","funding_rate","oi_change_3h_pct","flow_score","flow_state","discovery_score"):
     if row.get(k) not in (None,""):item[k]=row[k]
 return list(out.values())

def main():
 macro=load(LIVE/"global_macro_intelligence.json",{})
 cross=load(LIVE/"cross_asset_impact.json",{})
 flow=load(LIVE/"capital_flow_intelligence.json",{})
 crypto=extract_crypto()
 theme=str(macro.get("primary_theme") or "none")
 mechanism=MECHANISMS.get(theme,{"event":"no mapped macro shock","channels":["monitor liquidity, rates, USD, equities, commodities and crypto-specific flows"],"sectors":[],"watch":["USD","rates","equities","commodities","BTC","ETH"],"crypto_rule":"No directional conclusion without contemporaneous evidence."})
 btc=next((x for x in crypto if x.get("symbol")=="BTC"),None)
 eth=next((x for x in crypto if x.get("symbol")=="ETH"),None)
 current={
  "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),"status":"READY",
  "knowledge":{"asset_ontology":ASSET_ONTOLOGY,"finance_map":FINANCE_MAP,"chart_curriculum":CHART_CURRICULUM,
   "principles":["price is an observation, not an explanation","volume measures participation, not intent","funding and open interest describe positioning context, not guaranteed direction","relative strength separates broad market movement from asset-specific strength","macro is context; crypto-specific evidence remains necessary"]},
  "current_market_lens":{"macro_theme":theme,"macro_event_count":macro.get("event_count",0),"mechanism":mechanism,
   "cross_asset_watchlist":cross.get("cross_asset_watchlist",[]),"flow_rotation_state":flow.get("rotation_state","UNKNOWN"),
   "btc_observation":btc,"eth_observation":eth,"crypto_observations":crypto[:100]},
  "scenario_engine":MECHANISMS,
  "learning":{"mode":"CONTINUOUS_KEYLESS","minimum_observations_for_promotion":3,
   "next_targets":["cross-asset lead/lag","BTC breadth and dominance when verified","stablecoin liquidity proxies","derivatives positioning","macro surprise versus expectations when verified","sector transmission","historical regime comparison"]},
  "guardrails":["Macro events do not automatically predict BTC or any coin.","Never infer future direction from one observation.","Never infer whale activity from volume alone.","Never label an asset universally safest.","Never let this layer override existing evidence, safety or publication gates."]
 }
 LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(current,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 old=load(MEMORY,{"observation_counts":{}})
 counts=old.get("observation_counts") if isinstance(old.get("observation_counts"),dict) else {}
 if theme!="none":counts[theme]=int(counts.get(theme,0))+1
 state={"version":"1.0","updated_at":current["generated_at"],"learning_mode":"CONTINUOUS_KEYLESS","observation_counts":counts,
        "repeatable_themes":sorted([k for k,v in counts.items() if int(v)>=3]),"minimum_observations_for_promotion":3}
 MEMORY.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 REPORT.write_text(json.dumps({"version":"1.0","status":"READY","macro_theme":theme,"crypto_observations":len(crypto),
   "chart_concepts":sum(len(v) for v in CHART_CURRICULUM.values()),"finance_concepts":sum(len(v) for v in FINANCE_MAP.values()),
   "repeatable_themes":state["repeatable_themes"],"continuous_learning":True},indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":"READY","macro_theme":theme,"crypto_observations":len(crypto),"repeatable_themes":state["repeatable_themes"]}))
if __name__=="__main__":raise SystemExit(main())
