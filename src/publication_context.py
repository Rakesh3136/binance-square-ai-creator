"""Lock the production-cycle identity and publication package before AI generation.

Creator 6.0: full-market newsroom/analyst mode.  News is an input lane, not an
automatic reason to publish an article.  The story director explicitly chooses
article mode; otherwise the normal TradingView/image format is used.

The final handoff also binds the current Binance Square monetization intelligence
contract so downstream generation uses the same verified attribution rules.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/publication_context.json'
MONETIZATION=ROOT/'data/intelligence/square_monetization_strategy.json'; MONETIZATION_OS=ROOT/'data/live/nic_monetization_contract.json'
ALIASES={'bitcoin':'BTC','btc':'BTC','ether':'ETH','ethereum':'ETH','eth':'ETH','binance coin':'BNB','bnb':'BNB','solana':'SOL','sol':'SOL','xrp':'XRP','ripple':'XRP','dogecoin':'DOGE','doge':'DOGE','cardano':'ADA','ada':'ADA','avalanche':'AVAX','avax':'AVAX','chainlink':'LINK','link':'LINK','zcash':'ZEC','zec':'ZEC','tron':'TRX','trx':'TRX','polkadot':'DOT','dot':'DOT','shiba inu':'SHIB','shib':'SHIB','sui':'SUI','toncoin':'TON','ton':'TON','pepe':'PEPE','floki':'FLOKI'}
def load(rel):
 p=ROOT/rel
 try:
  x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
 except Exception:return {}
def load_monetization():
 try:
  x=json.loads(MONETIZATION.read_text(encoding='utf-8')) if MONETIZATION.exists() else {}
  return x if isinstance(x,dict) else {}
 except Exception:return {}
def clean(v):return str(v or '').upper().replace('USDT','').replace('$','').strip()
def title_assets(title):
 t=str(title or '').lower(); found=[]
 for name,sym in sorted(ALIASES.items(),key=lambda x:-len(x[0])):
  if re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',t) and sym not in found:found.append(sym)
 return found
def resolve_editorial_state(frozen, preflight, eligibility):
 selected=preflight.get('selected_opportunity') if isinstance(preflight.get('selected_opportunity'),dict) else {}
 handoff=preflight.get('editorial_authoritative_handoff') if isinstance(preflight.get('editorial_authoritative_handoff'),dict) else {}
 eligible_selected=eligibility.get('selected') if isinstance(eligibility.get('selected'),dict) else {}
 frozen_symbol=clean(frozen.get('symbol'))
 handoff_symbol=clean(handoff.get('symbol'))
 synced=handoff.get('status')=='SYNCED' and bool(frozen_symbol) and handoff_symbol==frozen_symbol
 timing_state=str(handoff.get('timing_state') or selected.get('timing_state') or eligible_selected.get('timing_state') or '').upper()
 timing_reason=str(selected.get('reason') or eligible_selected.get('timing_reason') or frozen.get('reason') or '')
 if synced:
  category=str(selected.get('category') or frozen.get('category') or 'research_insight').lower()
  if timing_state=='EXHAUSTED':
   category='research_insight'
  lane=category
 else:
  category=str(frozen.get('category') or selected.get('category') or 'market_opportunity').lower()
  lane=category
 instruction=str(selected.get('instruction') or frozen.get('instruction') or '')
 if timing_state=='EXHAUSTED' and synced:
  instruction=("Explain the observed market move and the evidence gaps. State that timing is "
    "exhausted for a fresh entry; do not provide entry, stop-loss, or target levels "
    "or imply the move is actionable.")
 return {"synced":synced,"category":category,"content_lane":lane,
         "timing_state":timing_state,"timing_reason":timing_reason,
         "instruction":instruction}


def main():
 frozen=load('data/live/authoritative_opportunity.json'); brain=load('data/live/creator_brain_decision.json'); pre=load('data/live/editorial_preflight.json'); director=load('data/live/content_director_brief.json'); engagement=pre.get('engagement_strategy') or {}; experiment=engagement.get('experiment') or {}; selected=pre.get('selected_opportunity') or {}; monetization=load_monetization(); monetization_os=load('data/live/nic_monetization_contract.json')
 eligibility=load('data/live/nic22_5_publication_eligibility.json')
 editorial=resolve_editorial_state(frozen,pre,eligibility)
 symbol=clean(frozen.get('symbol')) or clean(brain.get('symbol')) or clean(selected.get('symbol'))
 if not symbol:raise SystemExit('No authoritative publication symbol')
 fs=clean(frozen.get('symbol')); bs=clean(brain.get('symbol'))
 if fs and bs and fs!=bs:raise SystemExit(f'Asset drift detected: frozen={fs}, brain={bs}')
 title=str(selected.get('news_title') or frozen.get('news_title') or '').strip(); news_authoritative=bool(title)
 if selected.get('symbol') and clean(selected.get('symbol'))!=symbol and not news_authoritative:raise SystemExit(f'Asset drift detected: frozen={symbol}, selected={clean(selected.get("symbol"))}')
 category=editorial["category"] or str(director.get('primary_story',{}).get('lane') or ('breaking_news' if news_authoritative else 'market_opportunity')).lower()
 os_lane=editorial["content_lane"] if editorial["synced"] else str(monetization_os.get('content_lane') or '').lower()
 resolved_lane=editorial["content_lane"] or os_lane or category
 if editorial["timing_state"]=="EXHAUSTED" and editorial["synced"]:
  resolved_lane="research_insight"
 fmt=('RESEARCH BRIEF' if editorial["timing_state"]=="EXHAUSTED" and editorial["synced"] else str(monetization_os.get('content_format') or brain.get('editorial_format') or director.get('recommended_format') or experiment.get('format') or 'NEWS REACTION').upper())
 requested=[]
 for obj in (brain.get('visual_decision') or {},director.get('visual_plan') or {}):
  for x in obj.get('chart_symbols') or obj.get('symbols') or []:
   s=clean(x)
   if s and s not in requested:requested.append(s)
 headline_assets=title_assets(title)
 for s in headline_assets:
  if s!=symbol and s not in requested:requested.append(s)
 pair_requested=category=='comparison' or str((brain.get('visual_decision') or {}).get('layout') or '').lower()=='pair' or any(s!=symbol for s in headline_assets)
 chart_symbols=[symbol]
 if pair_requested:
  for s in requested:
   if s!=symbol:chart_symbols.append(s)
 news_source=str(selected.get('news_source') or frozen.get('news_source') or '').strip()
 explicit_article = str(director.get('publication_mode') or director.get('format_mode') or '').strip().lower() == 'article' or str(brain.get('publication_mode') or '').strip().lower() == 'article'
 publication_mode='article' if explicit_article else 'image'
 visual_decision={**(brain.get('visual_decision') or {}),'type':'candlestick_chart','use_visual':True,'required':True,'provider':'TradingView','timeframe':'1H','chart_symbols':chart_symbols,'layout':'pair' if len(chart_symbols)>1 else 'single'}
 contract=monetization.get('monetization_contract') or {}
 wte=monetization.get('official_write_to_earn') or {}
 context={'version':6.0,'monetization_intelligence_version':str(monetization.get('version') or '2.0'),'locked_at':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'symbol_usdt':symbol+'USDT','category':category,'opportunity_score':float(frozen.get('score',0) or 0),'reason':editorial["timing_reason"] or str(frozen.get('reason') or brain.get('reason') or ''),'instruction':editorial["instruction"]),'editorial_format':fmt,'story_engine':('RESEARCH_INSIGHT' if editorial["timing_state"]=="EXHAUSTED" and editorial["synced"] else str(brain.get('story_engine') or director.get('narrative_engine') or 'FULL_MARKET_NEWSROOM')),'conversation_goal':str(brain.get('conversation_goal') or 'specific_reply'),'publication_mode':publication_mode,'article_title':title[:180] if publication_mode=='article' else '','news_title':title[:240],'news_source':news_source,'headline_assets':headline_assets,'chart_symbols':chart_symbols,'experiment_id':str(monetization_os.get('experiment_id') or engagement.get('experiment_id') or experiment.get('id') or frozen.get('experiment_id') or ''),'experiment_format':str(monetization_os.get('content_format') or experiment.get('format') or fmt),'experiment_hook':str(monetization_os.get('hook_type') or experiment.get('hook') or ''),'experiment_question':str(experiment.get('question') or ''),'cycle_id':str(monetization_os.get('cycle_id') or ''),'campaign_day':monetization_os.get('campaign_day'),'content_lane':resolved_lane,'content_lane_goal':(str(monetization_os.get('lane_goal') or '') if not editorial["synced"] else ''),'content_format':str(monetization_os.get('content_format') or fmt),'hook_type':str(monetization_os.get('hook_type') or ''),'visual_type':str(monetization_os.get('visual_type') or ''),'reader_payoff_type':str(monetization_os.get('reader_payoff_type') or ''),'experiment_variable':str(monetization_os.get('experiment_variable') or ''),'experiment_treatment':str(monetization_os.get('experiment_treatment') or ''),'monetization_os_version':str(monetization_os.get('version') or ''),'market_phase':str(brain.get('market_phase') or 'UNKNOWN'),'timing_state':editorial["timing_state"],'timing_reason':editorial["timing_reason"],'research_observation':eligible_selected.get('research') if isinstance(eligible_selected.get('research'),dict) else {},'editorial_authoritative_handoff':editorial["synced"],'visual_decision':visual_decision,'content_coverage':engagement.get('content_coverage') or [],'style_rule':str(engagement.get('style_rule') or ''),'hook_rule':str(engagement.get('hook_rule') or ''),'question_rule':str(engagement.get('question_rule') or ''),'writing_rule':str(engagement.get('writing_rule') or ''),'technical_rule':str(engagement.get('technical_rule') or ''),'creator_tracking_rule':str(engagement.get('creator_tracking_rule') or ''),'growth_rule':str(engagement.get('growth_rule') or ''),'monetization_rule':str(engagement.get('monetization_rule') or contract),'monetization_contract':contract,'write_to_earn_rules':wte,'selection_principles':monetization.get('selection_principles') or contract.get('priority_order') or [],'creatorpad_principles':monetization.get('creatorpad_principles') or {},'learning_snapshot':monetization.get('learning_snapshot') or {},'source':'frozen opportunity + Creator Brain + Content Director + engagement strategy + Square monetization intelligence + fresh news','guardrail':'Creator 6.0 covers the full crypto market. News is one opportunity lane, not an automatic article trigger. Frozen primary asset is authoritative. Monetization intelligence changes content quality/attribution preparation, never the truth of market data or reader activity. No arbitrary fallback asset is added. No revenue, trade, outcome or campaign reward is invented.'}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(context,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(context,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
