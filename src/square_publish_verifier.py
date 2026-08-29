"""Verify a Binance Square publication result before marking a cycle successful."""
from __future__ import annotations
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'data/live/publish_result.json'
STATUS=ROOT/'data/live/publication_verification.json'
def main():
 text=''
 for p in [ROOT/'/tmp/publish-result.txt',Path('/tmp/publish-result.txt')]:
  if p.exists(): text=p.read_text(encoding='utf-8',errors='replace');break
 # Also accept a persisted publisher result if the workflow writes JSON.
 if not text and RESULT.exists(): text=RESULT.read_text(encoding='utf-8',errors='replace')
 mid=re.search(r'\bID:\s*([^\s]+)',text); link=re.search(r'\bLink:\s*(https?://\S+)',text)
 ok=bool(mid and mid.group(1) not in {'unavailable','None','null'})
 data={'status':'VERIFIED' if ok else 'UNVERIFIED','post_id':mid.group(1) if ok else None,'link':link.group(1).rstrip('.,') if link else None,'evidence':'publisher output'}
 STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps(data));sys.exit(0 if ok else 2)
if __name__=='__main__':main()
