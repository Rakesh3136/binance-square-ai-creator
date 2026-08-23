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
    preflight['creator_brain_decision']=decision
    strategy=preflight.setdefault('engagement_strategy',{})
    if decision.get('editorial_format'): strategy['creator_brain_format']=decision['editorial_format']
    if decision.get('conversation_goal'): strategy['conversation_goal']=decision['conversation_goal']
    if decision.get('symbol'): strategy['creator_brain_symbol']=decision['symbol']
    PREFLIGHT.write_text(json.dumps(preflight,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'OK','format':decision.get('editorial_format'),'symbol':decision.get('symbol')}))

if __name__=='__main__': main()
