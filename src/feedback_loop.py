"""Turn observed post metrics into strategy feedback without inventing data."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG=Path('analytics/publication_log.jsonl')
OUT=Path('data/live/feedback_strategy.json')

def num(v):
    try:return float(v)
    except:return 0.0

def main():
    rows=[]
    if LOG.exists():
        for line in LOG.read_text(encoding='utf-8').splitlines():
            try: rows.append(json.loads(line))
            except: pass
    groups=defaultdict(lambda:{'posts':0,'views':0,'likes':0,'replies':0,'shares':0,'followers':0})
    for r in rows:
        key=str(r.get('experiment_id') or r.get('editorial_experiment') or r.get('format') or 'unknown')
        g=groups[key]; g['posts']+=1
        for k in ('views','likes','replies','shares','followers_gained'):
            target='followers' if k=='followers_gained' else k
            g[target]+=num(r.get(k))
    ranked=[]
    for key,g in groups.items():
        views=g['views']
        ranked.append({**g,'experiment':key,'reply_rate':g['replies']/views if views else 0,'like_rate':g['likes']/views if views else 0,'follower_rate':g['followers']/views if views else 0})
    ranked.sort(key=lambda x:(x['reply_rate']*0.5+x['follower_rate']*0.35+x['like_rate']*0.15),reverse=True)
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'observations':len(rows),'ranked_experiments':ranked,'rules':['Never infer performance when metrics are missing.','Do not optimize for views alone.','Require multiple observations before declaring a winner.','Increase testing of formats with stronger reply/follower rates.','Keep weak formats in rotation so the system does not overfit.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
