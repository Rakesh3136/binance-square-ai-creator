"""Mark a verified result follow-up announced only after publication truth."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];QUEUE=ROOT/'data/live/result_followup_queue.json';TRUTH=ROOT/'data/live/creator_20_0_publication_truth.json';STATE=ROOT/'analytics/result_followup_state.json'
def main():
    try:q=json.loads(QUEUE.read_text(encoding='utf-8'));t=json.loads(TRUTH.read_text(encoding='utf-8'))
    except Exception as e:print(json.dumps({'status':'SKIP','reason':str(e)}));return
    if not q.get('queued') or t.get('truth_state')!='VERIFIED_PUBLISHED':print(json.dumps({'status':'SKIP','reason':'publication_not_verified'}));return
    state={}
    if STATE.exists():
        try:state=json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:state={}
    ids=set(str(x) for x in state.get('announced_call_ids',[]));ids.add(str(q.get('call_id')));state.update({'updated_at':datetime.now(timezone.utc).isoformat(),'announced_call_ids':sorted(ids),'last_post_id':t.get('latest_publication',{}).get('post_id')});STATE.parent.mkdir(parents=True,exist_ok=True);STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8');QUEUE.write_text(json.dumps({'queued':False,'announced':True,'call_id':q.get('call_id'),'post_id':t.get('latest_publication',{}).get('post_id')},indent=2),encoding='utf-8');print(json.dumps(state,indent=2))
if __name__=='__main__':main()
