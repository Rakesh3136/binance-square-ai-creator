"""Content Master Router for differentiated, evidence-backed Square publishing."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREF=ROOT/"data/live/editorial_preflight.json"
DIRECTOR=ROOT/"data/live/content_director_brief.json"
AUD=ROOT/"data/live/audience_growth_director.json"
LEARN=ROOT/"data/live/creator_self_training.json"
MACRO=ROOT/"data/live/global_macro_intelligence.json"
IMPACT=ROOT/"data/live/cross_asset_impact.json"
OUT=ROOT/"data/live/content_master_route.json"
LANES={
 "capital_flow_long":("signal","CAPITAL FLOW LONG THESIS","capital_flow_long","tradingview"),
 "capital_flow_short":("signal","CAPITAL FLOW SHORT THESIS","capital_flow_short","tradingview"),
 "technical_setup":("signal","TRADINGVIEW DECISION CHART","technical_setup","tradingview"),
 "creator_signal_outcome":("accountability","CALL OUTCOME / ACCOUNTABILITY","creator_signal_outcome","tradingview"),
 "follow_up":("accountability","FOLLOW-UP / UPDATE","follow_up","tradingview"),
 "breaking_news":("news","BREAKING NEWS + MARKET IMPACT","breaking_news","tradingview"),
 "news_and_macro":("news_macro","MACRO EVENT → CRYPTO IMPACT","news_and_macro","tradingview"),
 "watchlist":("research","DEEP RESEARCH RADAR","watchlist","tradingview"),
 "comparison":("research","COIN VS COIN","comparison","tradingview"),
 "education":("education","ONE CHART / ONE LESSON","education","optional"),
 "top_gainers":("discovery","MOMENTUM EXPLAINER","top_gainers","tradingview"),
 "top_losers":("discovery","BREAKDOWN / FAKEOUT ANALYSIS","top_losers","tradingview"),
 "high_volatility":("discovery","VOLATILITY + TEST","high_volatility","tradingview"),
 "volume_leaders":("discovery","DATA SURPRISE","volume_leaders","tradingview"),
 "new_listings":("discovery","PRICE DISCOVERY WATCH","new_listings","tradingview"),
 "crypto_meme":("meme","CRYPTO MEME + MARKET CONTEXT","crypto_meme","meme"),
}
def load(p):
 try:
  x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
 except Exception:return {}
def main():
 pre,director,aud,learn,macro,impact=map(load,(PREF,DIRECTOR,AUD,LEARN,MACRO,IMPACT))
 selected=pre.get("selected_opportunity") or (aud.get("selected") if isinstance(aud.get("selected"),dict) else {})
 cat=str(selected.get("category") or (director.get("primary_story") or {}).get("lane") or "").lower()
 if cat not in LANES:
  cat="capital_flow_long" if str(selected.get("direction") or "").upper()=="LONG" else "capital_flow_short" if str(selected.get("direction") or "").upper()=="SHORT" else "news_and_macro" if macro.get("event_count") else "watchlist"
 family,fmt,narrative,visual=LANES[cat]
 macro_event=macro.get("primary_theme") or "none"
 impact_signal=(impact.get("selected_impact") or {}) if isinstance(impact.get("selected_impact"),dict) else {}
 route={
  "version":"1.0",
  "generated_at":datetime.now(timezone.utc).isoformat(),
  "category":cat,
  "content_family":family,
  "format":fmt,
  "narrative_engine":narrative,
  "visual_mode":visual,
  "symbol":str(selected.get("symbol") or "").upper().replace("USDT","").replace("$",""),
  "reason":"Content Master maps the authoritative opportunity to the right publishing form; self-training only influences bounded preferences.",
  "macro_context":{"primary_theme":macro_event,"event_count":macro.get("event_count",0),"impact_ready":bool(impact_signal or impact)},
  "learning":{"plan_id":learn.get("plan_id"),"next_experiment":(learn.get("policy") or {}).get("next_experiment"),"underrepresented_lanes":(learn.get("policy") or {}).get("underrepresented_lanes",[])},
  "monetization":{"cashtag_required":True,"verified_widget_preferred":True,"quality_over_clicks":True,"eligible_content_note":"Use only formats supported by the publisher; do not claim unavailable video/live capabilities."},
  "rules":{"signal_requires_verified_setup":True,"non_signal_requires_verified_event_or_market_evidence":True,"meme_is_secondary":True,"never_force_weak_story":True,"never_infer_revenue":True}
 }
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(route,indent=2,ensure_ascii=False)+"\\n",encoding="utf-8")
 pre["content_master_route"]=route
 PREF.write_text(json.dumps(pre,indent=2,ensure_ascii=False)+"
",encoding="utf-8")
 print(json.dumps(route,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
