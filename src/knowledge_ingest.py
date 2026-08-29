"""Safe knowledge-ingestion registry.

Records approved documentation/release-note sources for later retrieval. Raw
external material is never executed or treated as trusted code. This keeps the
knowledge layer expandable without turning arbitrary web content into code.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'data/intelligence/knowledge_sources.json'
DIG=ROOT/'data/intelligence/knowledge_ingestion_log.jsonl'
DEFAULT=[
 {'name':'Python documentation','url':'https://docs.python.org/3/','domain':'python'},
 {'name':'GitHub Actions documentation','url':'https://docs.github.com/en/actions','domain':'github_actions'},
 {'name':'Git documentation','url':'https://git-scm.com/docs','domain':'git'},
 {'name':'Google GenAI documentation','url':'https://ai.google.dev/gemini-api/docs','domain':'ai'},
 {'name':'Binance developer documentation','url':'https://developers.binance.com/','domain':'binance'},
]
def main():
 REG.parent.mkdir(parents=True,exist_ok=True)
 if REG.exists():
  try:s=json.loads(REG.read_text(encoding='utf-8'))
  except:s={}
 else:s={}
 sources=s.get('sources',[]) if isinstance(s,dict) else []
 known={x.get('url') for x in sources}
 now=datetime.now(timezone.utc).isoformat()
 for x in DEFAULT:
  if x['url'] not in known:sources.append({**x,'source_id':hashlib.sha256(x['url'].encode()).hexdigest()[:16],'approved':True,'added_at':now})
 REG.write_text(json.dumps({'updated_at':now,'sources':sources},indent=2,ensure_ascii=False),encoding='utf-8')
 with DIG.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':now,'event':'source_registry_refresh','source_count':len(sources)})+'\n')
 print(json.dumps({'status':'OK','source_count':len(sources)}))
if __name__=='__main__':main()
