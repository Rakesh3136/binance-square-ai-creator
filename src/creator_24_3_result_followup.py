"""Creator 24.3 — automatic public call-check queue.

When a previously published prediction reaches a verified terminal outcome, build
one concise, timestamped follow-up draft. The original call is never rewritten.
The queue is marked announced only after Binance publication succeeds.
"""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/live/result_followup_queue.json';REPORT_DIR=ROOT/'data/reports';STATE=ROOT/'analytics/result_followup_state.json';OUTCOMES=ROOT/'analytics/prediction_outcomes.jsonl'
def jsonl(p):
    if not p.exists():return []
    out=[]
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict):out.append(x)
        except Exception:pass
    return out
def main():
    state={}
    if STATE.exists():
        try:state=json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:state={}
    announced=set(str(x) for x in state.get('announced_call_ids',[]))
    terminal=[x for x in jsonl(OUTCOMES) if x.get('outcome') in {'WIN','INVALIDATED','LOSS'} and str(x.get('call_id') or '') not in announced]
    if not terminal:
        OUT.write_text(json.dumps({'queued':False,'reason':'no_unannounced_terminal_outcome'},indent=2),encoding='utf-8');print(json.dumps({'queued':False}));return
    x=terminal[-1];sym=str(x.get('symbol') or '').upper();direction=str(x.get('direction') or '').replace('_',' ').lower();outcome=str(x.get('outcome'));ref=x.get('reference_price');target=x.get('hit_target');inv=x.get('invalidation');when=str(x.get('evaluated_at') or '')
    if outcome=='WIN':
        body=f"Call check: ${sym} {direction} setup reached the frozen target at {target}.\n\nThe original reference was ${ref}. Nothing was moved after publication; fresh 1H Binance candles confirmed the level.\n\nThat matters because a call is only useful if the thesis can be checked against a fixed level.\n\nSource: Binance 1H OHLCV. Checked {when}.\n\nWould you keep this setup on the same confirmation rule next time?"
    else:
        body=f"Call check: ${sym} {direction} setup was invalidated.\n\nThe original reference was ${ref}, with invalidation fixed at ${inv}. Fresh 1H Binance candles crossed that level, so the thesis is closed rather than moved.\n\nA public track record needs the misses as well as the wins.\n\nSource: Binance 1H OHLCV. Checked {when}.\n\nWould you have closed the idea at the same invalidation?"
    body=re.sub(r'\n{3,}','\n\n',body).strip()
    path=REPORT_DIR/f"result-followup-{x.get('call_id')}-multi-agent.json";report={'status':'DRAFT_ONLY_NOT_PUBLISHED','draft':{'post':body,'text':body,'symbol':sym,'category':'result_followup','quality_score':95,'visual_requested':False,'visual_type':'none'},'content_category':'result_followup','result_followup':{'call_id':x.get('call_id'),'outcome':outcome,'evaluated_at':when},'research':{'information_advantage_score':100,'source':'Binance 1H OHLCV'},'publish_rescue':False}
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'queued':True,'call_id':x.get('call_id'),'outcome':outcome,'draft_path':str(path)},indent=2),encoding='utf-8');print(json.dumps({'queued':True,'call_id':x.get('call_id'),'outcome':outcome,'draft_path':str(path)}))
if __name__=='__main__':main()
