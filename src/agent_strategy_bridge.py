"""Bind bounded agent strategy into the editorial contract."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; STRATEGY=ROOT/'data/live/agent_strategy.json'; FLOW=ROOT/'data/live/capital_flow_intelligence.json'
STYLE_TO_NARRATIVE={'flow_trader':'capital_flow','high_energy':'momentum_question','newsroom':'event_context_impact','technical_analyst':'level_confirmation','research_analyst':'research_radar','meme_creator':'crypto_meme','conversational':'what_to_watch'}
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def main():
    if not PREFLIGHT.exists() or not STRATEGY.exists():
        print('Agent strategy bridge: no strategy artifact; preserving existing contract'); return
    pre=load(PREFLIGHT); strategy=load(STRATEGY); flow=load(FLOW); selected=pre.get('selected_opportunity') or {}; d=pre.setdefault('content_director_4',{})
    authoritative=str(selected.get('symbol') or (d.get('primary_story') or {}).get('symbol') or '').upper().replace('USDT',''); agent_symbol=str(strategy.get('symbol') or '').upper().replace('USDT','')
    if authoritative and agent_symbol and authoritative!=agent_symbol: raise SystemExit(f'Agent strategy bridge: asset mismatch {authoritative} != {agent_symbol}')
    style=str(strategy.get('archetype') or '').strip(); narrative=STYLE_TO_NARRATIVE.get(style)
    if narrative and str(selected.get('category') or '').lower() not in {'capital_flow_long','capital_flow_short','crypto_meme'}: d['narrative_engine']=narrative
    setup=strategy.get('trade_setup') or {}
    if not setup:
        for x in flow.get('top_conditional_setups') or []:
            if str(x.get('symbol') or '').upper().replace('USDT','')==agent_symbol: setup=x.get('trade_setup') or x.get('prediction') or {}; break
    d.update({'agent_strategy_thesis':strategy.get('thesis'),'agent_archetype':style,'agent_one_authoring_pass':bool(strategy.get('one_authoring_pass',True)),'agent_evidence_only':bool(strategy.get('evidence_only',True)),'agent_strategy_version':strategy.get('version'),'agent_trade_setup':setup,'agent_prediction_contract':{'required':['direction','trigger','invalidation','tp1','tp2'],'conditional_only':True,'publish_only_when_supplied':True}})
    strategy['trade_setup']=setup; strategy['prediction_ready']=bool(setup); strategy['agent_council']={'research':'verify evidence','strategy':'choose thesis and conditional setup','risk':'define invalidation and scenarios','editorial':'human mobile narrative','outcome':'score prediction after publication','revenue':'observe qualified reader-intent only'}
    STRATEGY.write_text(json.dumps(strategy,indent=2,ensure_ascii=False),encoding='utf-8'); PREFLIGHT.write_text(json.dumps(pre,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','symbol':authoritative,'archetype':style,'narrative':narrative,'prediction_ready':bool(setup),'agents':list(strategy['agent_council'])}))
if __name__=='__main__':main()
