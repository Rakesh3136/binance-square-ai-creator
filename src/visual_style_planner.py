"""Choose a bounded visual treatment and avoid consecutive duplicates."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/visual_style_plan.json'
LOG=ROOT/'analytics/publication_log.jsonl'
STYLES=('decision_map','structure_breakout','fibonacci_context','volume_regime','structure_fibonacci')

def recent():
    if not LOG.exists():return []
    rows=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-30:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict) and str(x.get('status') or '').upper() in {'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_SUBMITTED_504'}:rows.append(x)
        except Exception:pass
    return rows[-12:]
def main():
    rows=recent(); counts=Counter(str(x.get('visual_style') or '') for x in rows); used=[x for x in counts if x]
    candidates=[x for x in STYLES if x not in used] or list(STYLES)
    selected=min(candidates,key=lambda x:(counts[x],STYLES.index(x)))
    plan={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'status':'READY','style':selected,'recent_style_counts':dict(counts),'styles':list(STYLES),'contract':{'presentation_only':True,'authoritative_levels_unchanged':True,'derived_fibonacci_is_context_only':True,'derived_trendline_is_context_only':True,'real_data_only':True}}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8');print(json.dumps(plan,indent=2))
if __name__=='__main__':main()
