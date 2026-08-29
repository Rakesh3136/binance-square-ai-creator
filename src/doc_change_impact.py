"""Turn monitored documentation changes into actionable engineering review items."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'data/intelligence/knowledge_change_log.jsonl'
OUT=ROOT/'data/intelligence/doc_change_impact.json'
def main():
 events=[]
 if LOG.exists():
  for line in LOG.read_text(encoding='utf-8').splitlines()[-100:]:
   try: events.append(json.loads(line))
   except: pass
 changed=[e for e in events if e.get('changed')]
 impacts=[]
 for e in changed:
  domain=e.get('domain','unknown'); impacts.append({'source':e.get('name'),'domain':domain,'priority':'HIGH' if domain in {'binance','github_actions','ai'} else 'MEDIUM','action':'Review current integration against the latest approved documentation before changing production code.'})
 result={'generated_at':datetime.now(timezone.utc).isoformat(),'changed_sources':len(changed),'impacts':impacts,'policy':'Documentation changes create review work; they never directly modify or deploy production code.'}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
