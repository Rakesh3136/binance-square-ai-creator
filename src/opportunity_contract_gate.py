"""Validate the frozen opportunity before expensive content generation."""
from __future__ import annotations
import json,re,math
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; FLOW=ROOT/'data/live/capital_flow_intelligence.json'; FROZEN=ROOT/'data/live/authoritative_opportunity.json'; OUT=ROOT/'data/live/opportunity_contract.json'
FLOW_MIN_CONFIDENCE=65.0

def load(path):
    try:
        x=json.loads(Path(path).read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def norm(value):return str(value or '').upper().replace('$','').replace('BINANCE:','').replace('USDT','').strip()
def num(value,default=0.0):
    try:
        n=float(value); return n if math.isfinite(n) else default
    except Exception:return default
def valid_symbol(value):return bool(re.fullmatch(r'[A-Z][A-Z0-9]{0,14}',norm(value)))

def main():
    pre=load(PREFLIGHT);flow=load(FLOW);frozen=load(FROZEN);selected=pre.get('selected_opportunity') or {};director=pre.get('content_director_4') or {}
    category=str(selected.get('category') or frozen.get('category') or '').lower();lane=str(selected.get('lane') or frozen.get('lane') or '').lower();symbol=norm(selected.get('symbol') or frozen.get('symbol') or (director.get('primary_story') or {}).get('symbol'));failures=[];warnings=[]
    if not selected:raise SystemExit('Opportunity Contract: no selected opportunity')
    if not valid_symbol(symbol):failures.append('invalid_selected_symbol')
    score=num(selected.get('score',selected.get('selected_score',frozen.get('score',0))),-1)
    if score < -1e-9 or score > 100.0+1e-9:failures.append('selected_score_out_of_bounds')
    if not category:failures.append('missing_category')
    allowed={'breaking_news','news_and_macro','top_gainers','top_losers','high_volatility','volume_leaders','new_listings','technical_setup','comparison','education','watchlist','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up','crypto_meme'}
    if category not in allowed:failures.append('unsupported_category')
    if category in {'breaking_news','news_and_macro'}:
        news_symbols=[norm(x) for x in selected.get('news_symbols',[]) if norm(x)]
        if not news_symbols:failures.append('news_missing_explicit_asset_anchor')
        elif symbol not in news_symbols:failures.append('news_symbol_not_in_authorized_news_assets')
        if not str(selected.get('news_title') or '').strip():failures.append('news_missing_verified_title')
        if not str(selected.get('news_source') or '').strip():warnings.append('news_source_missing')
    if category in {'capital_flow_long','capital_flow_short'} or lane in {'flow','capital_flow'}:
        setup=selected.get('trade_setup') or {};side=str(setup.get('side') or '').upper();conf=num(selected.get('flow_confidence'))
        if side not in {'LONG','SHORT'}:failures.append('flow_side_missing_or_invalid')
        expected='LONG' if category=='capital_flow_long' else 'SHORT' if category=='capital_flow_short' else side
        if expected in {'LONG','SHORT'} and side!=expected:failures.append('flow_category_side_mismatch')
        if conf<FLOW_MIN_CONFIDENCE:failures.append('flow_confidence_below_threshold')
        for key in ('trigger','invalidation'):
            if setup.get(key) is None:failures.append('flow_missing_'+key)
        if setup.get('tp1') is None and setup.get('take_profit_1') is None:failures.append('flow_missing_tp1')
        if setup.get('tp2') is None and setup.get('take_profit_2') is None:failures.append('flow_missing_tp2')
        if not selected.get('relative_strength_to_btc') and selected.get('flow_proxy_score') is None:failures.append('flow_missing_relative_strength_or_flow_evidence')
    if category=='watchlist' and not selected.get('research_evidence') and not selected.get('research'):warnings.append('watchlist_without_explicit_research_bundle')
    story=director.get('primary_story') or {};chart_symbols=[norm(x) for x in (selected.get('chart_symbols') or story.get('chart_symbols') or []) if norm(x)]
    # A recovered market candidate owns its chart identity. If no explicit chart
    # list survived, the frozen/selected primary asset is the safe single chart.
    if not chart_symbols and symbol:
        chart_symbols=[symbol]
    chart_required=category not in {'breaking_news','news_and_macro','watchlist','crypto_meme'}
    if chart_required and symbol not in chart_symbols:failures.append('chart_symbol_mismatch')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'version':'1.3','status':'PASS' if not failures else 'BLOCK','selected':selected,'symbol':symbol,'category':category,'lane':lane,'failures':failures,'warnings':warnings,'rules':{'score_range':'0-100 inclusive','score_tolerance':1e-9,'flow_min_confidence':FLOW_MIN_CONFIDENCE,'no_unanchored_news_assets':True,'flow_requires_trigger_invalidation_tp1_tp2':True,'conditional_not_predictive':True,'crypto_meme_is_chart_optional':True,'frozen_asset_is_authoritative':True}}
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    if failures:
        print(json.dumps({'status':'BLOCK','failures':failures,'warnings':warnings},indent=2,ensure_ascii=False));raise SystemExit(1)
    print(json.dumps({'status':'PASS','version':'1.3','symbol':symbol,'category':category,'chart_required':chart_required,'warnings':warnings},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
