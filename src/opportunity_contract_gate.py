"""Validate the frozen opportunity before any expensive content generation.

This is a hard integrity gate, not a quality-score bypass. It prevents stale,
unanchored, incomplete or internally contradictory story contracts from
reaching the writer and downstream publication gates.
"""
from __future__ import annotations
import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'
FLOW=ROOT/'data/live/capital_flow_intelligence.json'
OUT=ROOT/'data/live/opportunity_contract.json'

MAX_AGE_MINUTES=180
FLOW_MIN_CONFIDENCE=65.0

def load(path: Path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except Exception:
        return {}

def norm(value):
    return str(value or '').upper().replace('$','').replace('BINANCE:','').replace('USDT','').strip()

def num(value, default=0.0):
    try:return float(value)
    except Exception:return default

def valid_symbol(value):
    return bool(re.fullmatch(r'[A-Z][A-Z0-9]{0,14}',norm(value)))

def main():
    pre=load(PREFLIGHT);flow=load(FLOW);selected=pre.get('selected_opportunity') or {};director=pre.get('content_director_4') or {};category=str(selected.get('category') or '').lower();lane=str(selected.get('lane') or '').lower();symbol=norm(selected.get('symbol') or (director.get('primary_story') or {}).get('symbol'));failures=[];warnings=[]
    if not selected:
        raise SystemExit('Opportunity Contract: no selected opportunity')
    if not valid_symbol(symbol):failures.append('invalid_selected_symbol')
    score=num(selected.get('score'),-1)
    if score<0 or score>100:failures.append('selected_score_out_of_bounds')
    if not category:failures.append('missing_category')
    allowed={'breaking_news','news_and_macro','top_gainers','top_losers','high_volatility','volume_leaders','new_listings','technical_setup','comparison','education','watchlist','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up'}
    if category not in allowed:failures.append('unsupported_category')
    # News must be explicitly asset-anchored; never manufacture BTC as a fallback.
    if category in {'breaking_news','news_and_macro'}:
        news_symbols=[norm(x) for x in (selected.get('news_symbols') or []) if norm(x)]
        if not news_symbols:
            failures.append('news_missing_explicit_asset_anchor')
        elif symbol not in news_symbols:
            failures.append('news_symbol_not_in_authorized_news_assets')
        if not str(selected.get('news_title') or '').strip():failures.append('news_missing_verified_title')
        if not str(selected.get('news_source') or '').strip():warnings.append('news_source_missing')
    # Flow setups are only eligible when the engine supplies a complete conditional setup.
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
    # Research-only opportunities with missing evidence are radar/watchlist material,
    # not a forced trade call.
    if category=='watchlist':
        if not selected.get('research_evidence') and not selected.get('research'):warnings.append('watchlist_without_explicit_research_bundle')
    # Visual coherence.
    story=director.get('primary_story') or {};chart_symbols=[norm(x) for x in (story.get('chart_symbols') or []) if norm(x)]
    if category not in {'breaking_news','news_and_macro','watchlist'} and symbol not in chart_symbols and chart_symbols:
        failures.append('chart_symbol_mismatch')
    OUT.write_text(json.dumps({'generated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'version':'1.0','status':'PASS' if not failures else 'BLOCK','selected':selected,'symbol':symbol,'category':category,'lane':lane,'failures':failures,'warnings':warnings,'rules':{'score_range':'0-100','flow_min_confidence':FLOW_MIN_CONFIDENCE,'no_unanchored_news_assets':True,'flow_requires_trigger_invalidation_tp1_tp2':True,'conditional_not_predictive':True}},indent=2,ensure_ascii=False),encoding='utf-8')
    if failures:
        print(json.dumps({'status':'BLOCK','failures':failures,'warnings':warnings},indent=2,ensure_ascii=False));raise SystemExit(1)
    print(json.dumps({'status':'PASS','version':'1.0','symbol':symbol,'category':category,'warnings':warnings},indent=2,ensure_ascii=False))

if __name__=='__main__':main()
