"""Guard the learning loop against sparse or incomplete performance data."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

LOG=Path('analytics/publication_log.jsonl')
OUT=Path('data/live/metrics_integrity.json')
KEYS=['views','likes','replies','shares','followers_gained']

def val(r,k):
    if k not in r or r[k] is None or r[k]=='': return None
    try:return float(r[k])
    except:return None

def main():
    rows=[]
    if LOG.exists():
        for line in LOG.read_text(encoding='utf-8').splitlines():
            try: rows.append(json.loads(line))
            except: pass
    complete=0; partial=0; missing={k:0 for k in KEYS}
    for r in rows:
        got=0
        for k in KEYS:
            if val(r,k) is None: missing[k]+=1
            else: got+=1
        if got==len(KEYS): complete+=1
        elif got: partial+=1
    result={
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'rows':len(rows),'complete_rows':complete,'partial_rows':partial,
      'missing_metrics':missing,
      'learning_ready':complete>=5,
      'confidence_rule':'Do not declare a winning experiment/category with fewer than 5 complete observations.',
      'distribution_rule':'Views without engagement metrics remain an incomplete observation, not a zero-engagement verdict.',
      'next_action':'collect more measurements' if complete<5 else 'safe to compare experiments'
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
