from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
DECISION=ROOT/'data/live/creator_brain_decision.json'
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'


def main():
    decision=json.loads(DECISION.read_text()) if DECISION.exists() else {}
    preflight=json.loads(PREFLIGHT.read_text()) if PREFLIGHT.exists() else {}
    if not isinstance(decision,dict): decision={}
    if not isinstance(preflight,dict): preflight={}

    # Bridge Creator Brain -> the exact engagement structure consumed by
    # multi_agent_creator.py and its deterministic fallback. This makes the
    # decision operational rather than merely recording it in a sidecar file.
    preflight['creator_brain_decision']=decision
    strategy=preflight.setdefault('engagement_strategy',{})
    experiment=strategy.setdefault('experiment',{})

    if decision.get('editorial_format'):
        strategy['creator_brain_format']=decision['editorial_format']
        experiment['format']=decision['editorial_format']
    if decision.get('conversation_goal'):
        strategy['conversation_goal']=decision['conversation_goal']
    if decision.get('symbol'):
        strategy['creator_brain_symbol']=decision['symbol']
        preflight['selected_opportunity']=dict(preflight.get('selected_opportunity') or {})
        preflight['selected_opportunity']['symbol']=decision['symbol']
    if decision.get('decision'):
        strategy['creator_brain_decision']=decision['decision']
    if decision.get('reason'):
        strategy['creator_brain_reason']=decision['reason']

    # Preserve the experiment identifier while making the Brain's format the
    # authoritative editorial format for this production cycle.
    strategy['experiment']=experiment
    PREFLIGHT.write_text(json.dumps(preflight,indent=2,ensure_ascii=False))
    print(json.dumps({
        'status':'OK',
        'format':decision.get('editorial_format'),
        'symbol':decision.get('symbol'),
        'conversation_goal':decision.get('conversation_goal')
    }))

if __name__=='__main__': main()
