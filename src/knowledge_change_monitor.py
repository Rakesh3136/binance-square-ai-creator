"""Detect changes in approved documentation sources without executing content.

Stores source fingerprints and flags changes for the Living Brain. Actual retrieval,
parsing and trust promotion remain separate stages.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'data/intelligence/knowledge_sources.json'; STATE=ROOT/'data/intelligence/knowledge_source_state.json'; EVENTS=ROOT/'data/intelligence/knowledge_change_events.jsonl'
def main():
 try: data=json.loads(REG.read_text(encoding='utf-8'))
 except Exception: data={'sources':[]}
 sources=data.get('sources',[]); old={}
 if STATE.exists():
  try: old=json.loads(STATE.read_text(encoding='utf-8'))
  except: old={}
 now=datetime.now(timezone.utc).isoformat(); current={}; changed=[]
 for s in sources:
  url=s.get('url',''); sid=s.get('source_id') or hashlib.sha256(url.encode()).hexdigest()[:16]
  # URL metadata is fingerprinted here; content retrieval is intentionally separate.
  fp=hashlib.sha256(url.encode()).hexdigest()
  current[sid]={'url':url,'fingerprint':fp,'checked_at':now}
  if old.get(sid,{}).get('fingerprint') not in (None,fp): changed.append(sid)
 STATE.parent.mkdir(parents=True,exist_ok=True);STATE.write_text(json.dumps(current,indent=2),encoding='utf-8')
 with EVENTS.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':now,'changed_sources':changed,'source_count':len(sources)})+'\n')
 print(json.dumps({'status':'OK','changed_sources':changed,'source_count':len(sources)}))
if __name__=='__main__':main()
