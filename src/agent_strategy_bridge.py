"""Bind bounded agent strategy into the editorial contract.

The publication context is the single source of truth for the current cycle.
Agents can enrich the contract, but they must never replace the locked asset.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; CONTEXT=ROOT/'data/live/publication_context.json'; STRATEGY=ROOT/'data/live/agent_strategy.json'; FLOW=ROOT/'data/live/capital_flow_intelligence.json'
STYLE_TO_NARRATIVE={'flow_trader':'capital_flow','high_energy':'momentum_question','newsroom':'event_context_impact','technical_analyst':'level_confirmation','research_analyst':'research_radar','meme_creator':'crypto_meme','conversational':'what_to_watch'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean(v): return str(v or '').upper().replace('USDT','').replace('$','').strip()
def main():
    if not PREFLIGHT.exists() or not STRATEGY.exists():
        print('Agent strategy bridge: no strategy artifact; preserving existing contract'); return
    pre=load(PREFLIGHT); context=load(CONTEXT); strategy=load(STRATEGY); flow=load(FLOW); selected=pre.get('selected_opportunity') or {}; d=pre.setdefault('content_director_4',{})
    context_symbol=clean(context.get('symbol'))
    agent_symbol=clean(strategy.get('symbol'))
    selected_symbol=clean(selected.get('symbol'))
    # publication_context is authoritative. A stale selected_opportunity may be
    # retained from the previous cycle; it must never override the locked asset.
    authoritative=context_symbol or agent_symbol or selected_symbol
    if not authoritative:
        raise SystemExit('Agent strategy bridge: no authoritative publication asset')
    if agent_symbol and agent_symbol!=authoritative:
        raise SystemExit(f'Agent strategy bridge: asset mismatch {authoritative} != {agent_symbol}')
    # Normalize the downstream selection to the locked asset so stale preflight
    # state cannot poison authoring. Preserve the fresh fields that belong to
    # the current opportunity, but never carry an old symbol into the contract.
    if selected_symbol and selected_symbol!=authoritative:
        selected=dict(selected)
        selected['symbol']=authoritative
        selected['authoritative_asset_recovered']=True
        pre['selected_opportunity']=selected
    style=str(strategy.get('archetype') or '').strip(); narrative=STYLE_TO_NARRATIVE.get(style)
    if narrative and str(selected.get('category') or '').lower() not in {'capital_flow_long','capital_flow_short','crypto_meme'}: d['narrative_engine']=narrative
    setup=strategy.get('trade_setup') or {}
    if not setup:
        for x in flow.get('top_conditional_setups') or []:
            if str(x.get('symbol') or '').upper().replace('USDT','')==authoritative: setup=x.get('trade_setup') or x.get('prediction') or {}; break
    d.update({'agent_strategy_thesis':strategy.get('thesis'),'agent_archetype':style,'agent_one_authoring_pass':bool(strategy.get('one_authoring_pass',True)),'agent_evidence_only':bool(strategy.get('evidence_only',True)),'agent_strategy_version':strategy.get('version'),'agent_trade_setup':setup,'agent_prediction_contract':{'required':['direction','trigger','invalidation','tp1','tp2'],'conditional_only':True,'publish_only_when_supplied':True},'authoritative_asset':authoritative})
    strategy['symbol']=authoritative; strategy['trade_setup']=setup; strategy['prediction_ready']=bool(setup); strategy['agent_council']={'research':'verify evidence','strategy':'choose thesis and conditional setup','risk':'define invalidation and scenarios','editorial':'human mobile narrative','outcome':'score prediction after publication','revenue':'observe qualified reader-intent only'}
    STRATEGY.write_text(json.dumps(strategy,indent=2,ensure_ascii=False),encoding='utf-8'); PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','symbol':authoritative,'archetype':style,'narrative':narrative,'prediction_ready':bool(setup),'agents':list(strategy['agent_council']),'stale_selection_recovered':bool(selected_symbol and selected_symbol!=authoritative)}))
if __name__=='__main__':main()
